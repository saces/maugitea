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
from typing import Type

from aiohttp.web import Response, Request
import giteapy

from maubot import Plugin, MessageEvent
from maubot.handlers import command, web
from mautrix.util.config import BaseProxyConfig

from .db import Database
from .config import Config

from pprint import pprint

class GiteaBot(Plugin):

    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()
        self.db = Database(self.database)

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config


    # region Webhook handling

    @web.post("/webhooks")
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
    async def whoami(self, evt: MessageEvent) -> None:
        await evt.reply(f"Not implementet yeeet.")

    # endregion
