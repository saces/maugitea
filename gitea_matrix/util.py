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
from typing import Any, Callable, Optional, Tuple

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

class ReposOrAliasArgument(Argument):
    def __init__(self, name: str, label: str = None,
                 *, required: bool = False):
        super().__init__(name, label=label, required=required, pass_raw=True)

    def match(self, val: str, evt: MessageEvent, instance: 'GiteaBot', **kwargs
              ) -> Tuple[str, Any]:
        vals = val.split(" ")

        repos = instance.db.get_repos_alias(evt.sender, vals[0])

        if repos:
            return " ".join(vals[1:]), repos
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

def sigil_int(val: str) -> int:
    if len(val) == 0:
        raise ValueError('No issue ID given')
    if val[0] == '#':
        return int(val[1:])
    return int(val)

def quote_parser(val: str, return_all: bool = False) -> Tuple[str, Optional[str]]:
    if len(val) == 0:
        return val, None

    if val[0] in ('"', "'"):
        try:
            next_quote = val.index(val[0], 1)
            return val[next_quote + 1:], val[1:next_quote]
        except ValueError:
            pass
    if return_all:
        return "", val
    vals = val.split("\n", 1)
    if len(vals) == 1:
        return "", vals[0]
    else:
        return vals[1], vals[0]
