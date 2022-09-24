import selenium.webdriver.remote.webelement


class WebElement(selenium.webdriver.remote.webelement.WebElement):
    """
    Custom WebElement class which makes it easier to view elements when
    working in an interactive environment.

    standard webelement repr:
    <selenium.webdriver.remote.webelement.WebElement (session="85ff0f671512fa535630e71ee951b1f2", element="6357cb55-92c3-4c0f-9416-b174f9c1b8c4")>

    using this WebElement class:
    <WebElement(<a class="mobile-show-inline-block mc-update-infos init-ok" href="#" id="main-cat-switcher-mobile">)>

    """

    @property
    def attrs(self):
        if not hasattr(self, "_attrs"):
            self._attrs = self._parent.execute_script(
                """
                var items = {}; 
                for (index = 0; index < arguments[0].attributes.length; ++index) 
                {
                 items[arguments[0].attributes[index].name] = arguments[0].attributes[index].value 
                }; 
                return items;
                """,
                self,
            )
        return self._attrs

    def __repr__(self):
        strattrs = " ".join([f'{k}="{v}"' for k, v in self.attrs.items()])
        if strattrs:
            strattrs = " " + strattrs
        return f"{self.__class__.__name__} <{self.tag_name}{strattrs}>"
