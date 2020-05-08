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
from typing import List, NamedTuple

from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint, String, Text, or_
from sqlalchemy.engine.base import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

from mautrix.types import UserID

AuthInfo = NamedTuple('AuthInfo', server=str, api_token=str)
AliasInfo = NamedTuple('AliasInfo', server=str, alias=str)
Base = declarative_base()

from pprint import pprint

class ServerAlias(Base):
    __tablename__ = "serveralias"

    user_id: UserID = Column(String(255), primary_key=True)
    alias = Column(Text, primary_key=True, nullable=False)
    gitea_server = Column(Text, primary_key=True)

class ServerToken(Base):
    __tablename__ = "servertoken"

    user_id: UserID = Column(String(255), primary_key=True, nullable=False)
    gitea_server = Column(Text, primary_key=True, nullable=False)
    api_token = Column(Text, nullable=False)

class RepositoryAlias(Base):
    __tablename__ = "repositoryalias"

    user_id: UserID = Column(String(255), primary_key=True)
    alias = Column(Text, primary_key=True, nullable=False)
    gitea_repository = Column(Text, primary_key=True)

class Database:
    db: Engine

    def __init__(self, db: Engine) -> None:
        self.db = db
        Base.metadata.create_all(db)
        self.Session = sessionmaker(bind=self.db)

    def add_server_alias(self, mxid: UserID, url: str, alias: str) -> None:
        s = self.Session()
        salias = ServerAlias(user_id=mxid, gitea_server=url, alias=alias)
        s.add(salias)
        s.commit()

    def get_server_aliases(self, user_id: UserID) -> List[AliasInfo]:
        s = self.Session()
        rows = s.query(ServerAlias).filter(ServerAlias.user_id == user_id)
        return [AliasInfo(row.gitea_server, row.alias) for row in rows]

    def get_server_alias(self, user_id: UserID, alias: str) -> str:
        s = self.Session()
        row = s.query(ServerAlias).filter(ServerAlias.user_id == user_id, ServerAlias.alias == alias).scalar()
        if row:
            return row.gitea_server
        return None

    def has_server_alias(self, user_id: UserID, alias: str) -> bool:
        s: Session = self.Session()
        return s.query(ServerAlias).filter(ServerAlias.user_id == user_id, ServerAlias.alias == alias).count() > 0

    def rm_server_alias(self, mxid: UserID, alias: str) -> None:
        s = self.Session()
        alias = s.query(ServerAlias).filter(ServerAlias.user_id == mxid,
                                      ServerAlias.alias == alias).one()
        s.delete(alias)
        s.commit()

    def get_servers(self, mxid: UserID) -> List[str]:
        s = self.Session()
        rows = s.query(ServerToken).filter(ServerToken.user_id == mxid)
        return [row.gitea_server for row in rows]

    def add_login(self, mxid: UserID, url: str, token: str) -> None:
        s = self.Session()
        s.add(ServerToken(user_id=mxid, gitea_server=url, api_token=token))
        s.commit()

    def rm_login(self, mxid: UserID, url: str) -> None:
        s = self.Session()
        token = s.query(ServerToken).get((mxid, url))
        s.delete(token)
        s.commit()

    def get_login(self, mxid: UserID, url: str) -> AuthInfo:
        s = self.Session()
        row = s.query(ServerToken).filter(ServerToken.user_id == mxid, ServerToken.gitea_server == url).one()
        return AuthInfo(server=row.gitea_server, api_token=row.api_token)

    def add_repos_alias(self, mxid: UserID, repos: str, alias: str) -> None:
        s = self.Session()
        ralias = RepositoryAlias(user_id=mxid, gitea_repository=repos, alias=alias)
        s.add(ralias)
        s.commit()

    def get_repos_aliases(self, user_id: UserID) -> List[AliasInfo]:
        s = self.Session()
        rows = s.query(RepositoryAlias).filter(RepositoryAlias.user_id == user_id)
        return [AliasInfo(row.gitea_repository, row.alias) for row in rows]

    def get_repos_alias(self, user_id: UserID, alias: str) -> str:
        s = self.Session()
        row = s.query(RepositoryAlias).filter(RepositoryAlias.user_id == user_id, RepositoryAlias.alias == alias).scalar()
        if row:
            return row.gitea_repository
        return None

    def has_repos_alias(self, user_id: UserID, alias: str) -> bool:
        s: Session = self.Session()
        return s.query(RepositoryAlias).filter(RepositoryAlias.user_id == user_id, RepositoryAlias.alias == alias).count() > 0

    def rm_repos_alias(self, mxid: UserID, alias: str) -> None:
        s = self.Session()
        ralias = s.query(RepositoryAlias).filter(RepositoryAlias.user_id == mxid,
                                                RepositoryAlias.alias == alias).one()
        s.delete(ralias)
        s.commit()
