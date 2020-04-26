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
from typing import Any, Tuple, Callable

import giteapy
from giteapy import Configuration as Gtc
from giteapy.rest import ApiException

from maubot import MessageEvent
from maubot.handlers.command import Argument

from .db import AuthInfo

from pprint import pprint

class UrlOrAliasArgument(Argument):
    def __init__(self, name: str, label: str = None,
                 *, required: bool = False):
        super().__init__(name, label=label, required=required, pass_raw=True)

    def match(self, val: str, evt: MessageEvent, instance: 'GiteaBot', **kwargs
              ) -> Tuple[str, Any]:
        vals = val.split(" ")

        serverurl = instance.db.get_server_alias(evt.sender, vals[0])

        if serverurl:
            return " ".join(vals[1:]), serverurl
        return " ".join(vals[1:]), vals[0]


Decoratable = Callable[['GiteaBot', MessageEvent, Gtc, Any], Any]
Decorator = Callable[['GiteaBot', MessageEvent, AuthInfo, Any], Any]

def with_gitea_session(func: Decoratable) -> Decorator:
    async def wrapper(self, evt: MessageEvent, url: str, **kwargs) -> Any:
        try:
            aInfo = self.db.get_login(evt.sender, url)
            gtc = giteapy.Configuration()
            gtc.host = aInfo.server
            gtc.api_key['access_token'] = aInfo.api_token
            return await func(self, evt, gtc=gtc, **kwargs)
        except ApiException as e:
            await evt.reply("Api Error.\n\n{0}".format(e))
        except Exception as e:
            self.log.error("Failed to handle command", exc_info=True)
            await evt.reply("Error.\n\n{0}".format(e))

    return wrapper
