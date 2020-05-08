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
from typing import List, Set, Type

from aiohttp.web import Response, Request
import asyncio
from asyncio import Task

from yarl import URL

import giteapy
from giteapy import Configuration as Gtc

from maubot import Plugin, MessageEvent
from maubot.handlers import command, event, web
from mautrix.types import EventType, Membership, MessageType, RoomID, StateEvent
from mautrix.util.config import BaseProxyConfig

from .db import Database
from .config import Config
from .util import UrlOrAliasArgument, with_gitea_session

from pprint import pprint


class GiteaBot(Plugin):
    task_list: List[Task]
    joined_rooms: Set[RoomID]

    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()
        self.db = Database(self.database)
        self.joined_rooms = set(await self.client.get_joined_rooms())
        self.task_list = []

    async def stop(self) -> None:
        if self.task_list:
            await asyncio.wait(self.task_list, timeout=1)

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
        if "X-Gitea-Event" not in request.headers:
            return Response(text="400: Bad request\n"
                                 "Event type not specified\n", status=400)
        if "X-Gitea-Delivery" not in request.headers:
            return Response(text="400: Bad request\n"
                                 "Missing delivery token header\n", status=401)
        if "X-Gitea-Signature" not in request.headers:
            return Response(text="400: Ba request\n"
                                 "Missing signature header\n", status=401)

        if "room" not in request.query:
            return Response(text="400: Bad request\n"
                                 "No room specified. Did you forget the '?room=' query parameter?\n",
                            status=400)

        if request.query["room"] not in self.joined_rooms:
            return Response(text="403: Forbidden\nThe bot is not in the room. "
                                 f"Please invite the bot to the room.\n", status=403)

        if request.headers.getone("Content-Type", "") != "application/json":
            return Response(status=406, text="406: Not Acceptable\n",
                            headers={"Accept": "application/json"})

        if not request.can_read_body:
            return Response(status=400, text="400: Bad request\n"
                                             "Missing request body\n")

        task = self.loop.create_task(self.process_hook_01(request))
        self.task_list += [task]
        return Response(status=202, text="202: Accepted\nWebhook processing started.\n")

    async def process_hook_01(self, req: Request) -> None:
        if self.config["send_as_notice"]:
            msgtype = MessageType.NOTICE
        else:
            msgtype = MessageType.TEXT

        try:
            msg = None
            body = await req.json()

            if body["secret"] != self.config["webhook-secret"]:
                self.log.error("Failed to handle Gitea event: secret doasnt match.")
            else:
                event = req.headers["X-Gitea-Event"]
                if event == 'push':
                    commits = body["commits"]
                    commit_count = len(commits)
                    if commit_count > 0:
                        msg = (f"user '{body['pusher']['login']}' pushed "
                               f"{commit_count} commit(s) to "
                               f"'{body['repository']['full_name']}' at '{URL(body['repository']['html_url']).host}'.")
                elif event == 'create':
                    msg = (f"user '{body['sender']['login']}' created a tag or branch in "
                           f"'{body['repository']['full_name']}' at '{URL(body['repository']['html_url']).host}'.")
                elif event == 'delete':
                    msg = (f"user '{body['sender']['login']}' deleted a tag or branch in "
                           f"'{body['repository']['full_name']}' at '{URL(body['repository']['html_url']).host}'.")
                else:
                    self.log.error(f"unhandled hook: {event}")
                    self.log.error(await req.text())

                room_id = RoomID(req.query["room"])
                if msg:
                    event_id = await self.client.send_markdown(room_id, msg, allow_html=True, msgtype=msgtype)

        except Exception:
            self.log.error("Failed to handle Gitea event", exc_info=True)

        task = asyncio.current_task()
        if task:
            self.task_list.remove(task)

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

    # region !gitea server alias

    @gitea.subcommand("alias", aliases=("a",),
                       help="Manage Gitea server aliases.")
    async def alias(self) -> None:
        pass

    @alias.subcommand("add", aliases=("a",), help="Add an alias to a Gitea server.")
    @command.argument("alias", "server alias")
    @command.argument("url", "server URL")
    async def alias_add(self, evt: MessageEvent, url: str, alias: str) -> None:
        if self.db.has_server_alias(evt.sender, alias):
            await evt.reply("Server alias already in use.")
            return
        self.db.add_server_alias(evt.sender, url, alias)
        await evt.reply(f"Added alias {alias} to server {url}")

    @alias.subcommand("list", aliases=("l", "ls"), help="Show your Gitea server aliases.")
    async def alias_list(self, evt: MessageEvent) -> None:
        aliases = self.db.get_server_aliases(evt.sender)
        if not aliases:
            await evt.reply("You don't have any server aliases.")
            return
        msg = ("You have the following server aliases:\n\n"
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

    # region !gitea repository alias

    @gitea.subcommand("ralias", aliases=("r",),
                       help="Manage Gitea repository aliases.")
    async def ralias(self) -> None:
        pass

    @ralias.subcommand("add", aliases=("a",), help="Add an alias to a Gitea repository.")
    @command.argument("alias", "repository alias")
    @command.argument("repos", "repository")
    async def ralias_add(self, evt: MessageEvent, repos: str, alias: str) -> None:
        if self.db.has_repos_alias(evt.sender, alias):
            await evt.reply("Repository alias already in use.")
            return
        self.db.add_repos_alias(evt.sender, repos, alias)
        await evt.reply(f"Added alias {alias} to repository {repos}")

    @ralias.subcommand("list", aliases=("l", "ls"), help="Show your Gitea repository aliases.")
    async def ralias_list(self, evt: MessageEvent) -> None:
        aliases = self.db.get_repos_aliases(evt.sender)
        if not aliases:
            await evt.reply("You don't have any repository aliases.")
            return
        msg = ("You have the following repository aliases:\n\n"
               + "\n".join(f"+ {alias.alias} → {alias.server}" for alias in aliases))
        await evt.reply(msg)

    @ralias.subcommand("remove", aliases=("r", "rm", "d", "del", "delete"),
                      help="Remove a alias to a Gitea repository.")
    @command.argument("alias", "repository alias")
    async def ralias_rm(self, evt: MessageEvent, alias: str) -> None:
        self.db.rm_repos_alias(evt.sender, alias)
        await evt.reply(f"Removed alias {alias}.")

    # endregion

