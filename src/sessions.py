import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import uuid1

from selenium.webdriver.chrome.webdriver import WebDriver

import utils


@dataclass
class Session:
    session_id: str
    driver: WebDriver
    created_at: datetime
    proxy: Optional[dict] = None
    user_agent: Optional[str] = None
    user_data_dir: Optional[str] = None
    browser_args: Optional[list] = None
    browser_executable_path: Optional[str] = None

    def lifetime(self) -> timedelta:
        return datetime.now() - self.created_at


class SessionsStorage:
    """SessionsStorage creates, stores and process all the sessions"""

    def __init__(self):
        self.sessions = {}

    def create(self, session_id: Optional[str] = None, proxy: Optional[dict] = None,
               user_agent: Optional[str] = None, user_data_dir: Optional[str] = None,
               browser_args: Optional[list] = None, browser_executable_path: Optional[str] = None,
               force_new: Optional[bool] = False) -> Tuple[Session, bool]:
        """create creates new instance of WebDriver if necessary,
        assign defined (or newly generated) session_id to the instance
        and returns the session object. If a new session has been created
        second argument is set to True.

        Note: The function is idempotent, so in case if session_id
        already exists in the storage a new instance of WebDriver won't be created
        and existing session will be returned. Second argument defines if 
        new session has been created (True) or an existing one was used (False).
        """
        session_id = session_id or str(uuid1())

        if force_new:
            self.destroy(session_id)

        if self.exists(session_id):
            return self.sessions[session_id], False

        driver = utils.get_webdriver(proxy=proxy, user_agent=user_agent, user_data_dir=user_data_dir,
                                     browser_args=browser_args, browser_executable_path=browser_executable_path)
        created_at = datetime.now()
        session = Session(session_id, driver, created_at, proxy=proxy, user_agent=user_agent,
                          user_data_dir=user_data_dir, browser_args=browser_args,
                          browser_executable_path=browser_executable_path)

        self.sessions[session_id] = session

        return session, True

    def exists(self, session_id: str) -> bool:
        return session_id in self.sessions

    def destroy(self, session_id: str) -> bool:
        """destroy closes the driver instance and removes session from the storage.
        The function is noop if session_id doesn't exist.
        The function returns True if session was found and destroyed,
        and False if session_id wasn't found.
        """
        if not self.exists(session_id):
            return False

        session = self.sessions.pop(session_id)
        if utils.PLATFORM_VERSION == "nt":
            session.driver.close()
        session.driver.quit()
        return True

    def get(self, session_id: str, ttl: Optional[timedelta] = None,
            proxy: Optional[dict] = None, user_agent: Optional[str] = None,
            user_data_dir: Optional[str] = None, browser_args: Optional[list] = None,
            browser_executable_path: Optional[str] = None) -> Tuple[Session, bool]:
        existing = self.sessions.get(session_id)
        if existing is not None:
            proxy = existing.proxy
            user_agent = existing.user_agent
            user_data_dir = existing.user_data_dir
            browser_args = existing.browser_args
            browser_executable_path = existing.browser_executable_path

        session, fresh = self.create(session_id, proxy=proxy, user_agent=user_agent,
                                     user_data_dir=user_data_dir, browser_args=browser_args,
                                     browser_executable_path=browser_executable_path)

        if ttl is not None and not fresh and session.lifetime() > ttl:
            logging.debug(f'session\'s lifetime has expired, so the session is recreated (session_id={session_id})')
            session, fresh = self.create(session_id, proxy=proxy, user_agent=user_agent,
                                         user_data_dir=user_data_dir, browser_args=browser_args,
                                         browser_executable_path=browser_executable_path, force_new=True)

        return session, fresh

    def session_ids(self) -> list[str]:
        return list(self.sessions.keys())
