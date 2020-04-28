# maugitea - A Gitea client and webhook receiver for maubot

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from typing import Set, Type

from aiohttp.web import Response, Request
from yarl import URL

import giteapy
from giteapy import Configuration as Gtc

from maubot import Plugin, MessageEvent
from maubot.handlers import command, event, web
from mautrix.types import EventType, Membership, RoomID, StateEvent
from mautrix.util.config import BaseProxyConfig

from .db import Database
from .config import Config
from .util import UrlOrAliasArgument, with_gitea_session

from pprint import pprint

class GiteaBot(Plugin):

    joined_rooms: Set[RoomID]

    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()
        self.db = Database(self.database)
        self.joined_rooms = set(await self.client.get_joined_rooms())

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    @event.on(EventType.ROOM_MEMBER)
    async def member_handler(self, evt: StateEvent) -> None:
        """
        updates the stored joined_rooms object whenever
        the bot joins or leaves a room.
        """
        if evt.state_key != self.client.mxid:
            return

        if evt.content.membership in (Membership.LEAVE, Membership.BAN):
            self.joined_rooms.remove(evt.room_id)
        if evt.content.membership == Membership.JOIN and evt.state_key == self.client.mxid:
            self.joined_rooms.add(evt.room_id)


    # region Webhook handling

    @web.post("/webhook/r0")
    async def post_handler(self, request: Request) -> Response:
        pprint(request)
        return Response(text="501: Not implemented yeeet.\n", status=501)

    # endregion

    @command.new(name="gitea", help="Manage this Gitea bot",
                  require_subcommand=True)
    async def gitea(self) -> None:
        pass

    # region extras (ping, whoami)

    @gitea.subcommand("ping", aliases=("p",), help="Ping the bot.")
    async def ping(self, evt: MessageEvent) -> None:
        await evt.reply("Pong")

    @gitea.subcommand("whoami", help="Check who you're logged in as.")
    @UrlOrAliasArgument("url", "server URL or alias")
    @with_gitea_session
    async def whoami(self, evt: MessageEvent, gtc: Gtc) -> None:
        api_instance = giteapy.UserApi(giteapy.ApiClient(gtc))
        api_response = api_instance.user_get_current()
        await evt.reply(f"You're logged into {URL(gtc.host).host} as "
                        f"{api_response.login}")

    # endregion

    # region !gitea alias

    @gitea.subcommand("alias", aliases=("a",),
                       help="Manage Gitea server aliases.")
    async def alias(self) -> None:
        pass

    @alias.subcommand("add", aliases=("a",), help="Add a alias to a Gitea server.")
    @command.argument("alias", "server alias")
    @command.argument("url", "server URL")
    async def alias_add(self, evt: MessageEvent, url: str, alias: str) -> None:
        if self.db.has_server_alias(evt.sender, alias):
            await evt.reply("Alias already in use.")
            return
        self.db.add_server_alias(evt.sender, url, alias)
        await evt.reply(f"Added alias {alias} to server {url}")

    @alias.subcommand("list", aliases=("l", "ls"), help="Show your Gitea server aliases.")
    async def alias_list(self, evt: MessageEvent) -> None:
        aliases = self.db.get_server_aliases(evt.sender)
        if not aliases:
            await evt.reply("You don't have any aliases.")
            return
        msg = ("You have the following aliases:\n\n"
               + "\n".join(f"+ {alias.alias} → {alias.server}" for alias in aliases))
        await evt.reply(msg)

    @alias.subcommand("remove", aliases=("r", "rm", "d", "del", "delete"),
                      help="Remove a alias to a Gitea server.")
    @command.argument("alias", "server alias")
    async def alias_rm(self, evt: MessageEvent, alias: str) -> None:
        self.db.rm_server_alias(evt.sender, alias)
        await evt.reply(f"Removed alias {alias}.")

    # endregion

    # region !gitea server

    @gitea.subcommand("server", aliases=("s",), help="Manage Gitea Servers.")
    async def server(self) -> None:
        pass

    @server.subcommand("list", aliases=("ls",), help="Show your Gitea servers.")
    async def server_list(self, evt: MessageEvent) -> None:
        servers = self.db.get_servers(evt.sender)
        if not servers:
            await evt.reply("You are not logged in to any server.")
            return
        await evt.reply("You are logged in to the following servers:\n\n"
                        + "\n".join(f"* {server}" for server in servers))

    @server.subcommand("login", aliases=("l",),
                       help="Add a Gitea access token for a Gitea server.")
    @UrlOrAliasArgument("url", "server URL or alias")
    @command.argument("token", "access token", pass_raw=True)
    async def server_login(self, evt: MessageEvent, url: str, token: str) -> None:
        # TODO verify the token
        self.db.add_login(evt.sender, url, token)
        await evt.reply(f"Added token for {url}.")

    @server.subcommand("logout", aliases=("rm",),
                       help="Remove the access token from the bot's database.")
    @UrlOrAliasArgument("url", "server URL or alias")
    async def server_logout(self, evt: MessageEvent, url: str) -> None:
        self.db.rm_login(evt.sender, url)
        await evt.reply(f"Removed {url} from the database.")

    # endregion
    