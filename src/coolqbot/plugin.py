""" 插件相关
"""
import configparser
import pickle
import re
from enum import Enum

from .exceptions import PluginNotExistError


class MessageType(Enum):
    """ 消息种类
    """
    All = 'message'
    Group = 'message.group'
    Private = 'message.private'


class Plugin:
    def __init__(self, bot, *events, data=False, config=False):
        self.name = self.__class__.__name__.lower()
        self._bot = bot
        self._events = events

        # 只有当插件需要保存数据时，才初始化 `data` 管理工具
        if data or config:
            self.data = PluginData(self.name,
                                self._bot.config['DATA_DIR_PATH'],
                                config=config)

    async def on_message(self, context):
        raise NotImplementedError

    def enable(self):
        for event in self._events:
            self._bot.subscribe(event.value, self.on_message)

    def disable(self):
        for event in self._events:
            self._bot.unsubscribe(event.value, self.on_message)

    def reload(self):
        raise NotImplementedError

    def status(self):
        raise NotImplementedError


class PluginData:
    """ 插件数据管理

    将插件数据保存在 `data` 文件夹对应的目录下。
    提供保存和读取文件/数据的方法。
    """

    def __init__(self, name, data_dir_path, config=False):
        # 插件名，用来确定插件的文件夹位置
        self._name = name
        self._base_path = data_dir_path / f'plugin-{name}'

        # 如果文件夹不存在则自动新建
        if not data_dir_path.exists():
            data_dir_path.mkdir()
        if not self._base_path.exists():
            self._base_path.mkdir()

        # 如果需要则初始化并加载配置
        if config:
            self._config_path = self._base_path / f'{self._name}.ini'
            self.config = configparser.ConfigParser()
            if self._config_path.exists():
                self._load_config()
            else:
                self._save_config()

    def save_pkl(self, data, filename):
        """ 保存到 `pkl` 文件
        """
        with self.open(f'{filename}.pkl', 'wb') as f:
            pickle.dump(data, f)

    def load_pkl(self, filename):
        """ 加载 `pkl` 文件
        """
        with self.open(f'{filename}.pkl', 'rb') as f:
            data = pickle.load(f)
        return data

    def config_get(self, section, option, fallback=None):
        """ 获得配置

        如果配置不存在则使用`fallback`并保存
        """
        try:
            value = self.config.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            if not fallback:
                raise
            value = fallback
            # 保存默认配置
            if section not in self.config.sections():
                self.config[section] = {}
            self.config.set(section, option, fallback)
            self._save_config()
        return value

    def config_set(self, section, option, value):
        """ 设置配置
        """
        if section not in self.config.sections():
            self.config[section] = {}
        self.config.set(section, option, value)
        self._save_config()

    def _load_config(self):
        """ 读取配置
        """
        self.config.read(self._config_path)

    def _save_config(self):
        """ 保存配置
        """
        with self.open(self._config_path, 'w') as configfile:
            self.config.write(configfile)

    def open(self, filename, open_mode='r'):
        """ 打开文件

        默认只读模式
        """
        path = self._base_path / filename
        return open(path, open_mode)

    def exists(self, filename):
        """ 判断文件是否存在
        """
        path = self._base_path / filename
        return path.exists()


class PluginManager:
    """ 插件管理器
    """

    def __init__(self, bot):
        self._plugin_prefix = 'plugins'
        self._plugin_list = {}
        self._bot = bot

    def _get_plugin_name(self, name):
        return f'{self._plugin_prefix}.{name}'

    def load_plugin(self):
        """ 加载插件
        """
        filenames = [
            x.stem for x in self._bot.config['PLUGINS_DIR_PATH'].iterdir()
            if x.is_file()
        ]
        for plugin_name in filenames:
            try:
                __import__(self._get_plugin_name(plugin_name))
                self._bot.logger.debug(f'Plugin [{plugin_name}] loaded.')
            except ImportError as e:
                self._bot.logger.error(
                    f'Import error: can not import [{plugin_name}], because {e}'
                )

    def enable_all(self):
        """ 启用所有插件
        """
        for plugin in self._plugin_list:
            self._plugin_list[plugin].enable()

    def disable_all(self):
        """ 禁用所有插件
        """
        for plugin in self._plugin_list:
            self._plugin_list[plugin].disable()

    def enable(self, name):
        """ 启用插件
        """
        if name in self._plugin_list:
            self._plugin_list[name].enable()
            self._bot.logger.info(f'已启用 {name}')
        else:
            raise PluginNotExistError()

    def disable(self, name):
        """ 禁用插件
        """
        if name in self._plugin_list:
            self._plugin_list[name].disable()
            self._bot.logger.info(f'已禁用 {name}')
        else:
            raise PluginNotExistError()

    def reload(self, name):
        """ 重载插件
        """
        if name in self._plugin_list:
            self._plugin_list[name].reload()
            self._bot.logger.info(f'已重载 {name}')
        else:
            raise PluginNotExistError()

    def status(self, name):
        """ 插件状态
        """
        if name in self._plugin_list:
            return self._plugin_list[name].status()
        else:
            raise PluginNotExistError()

    def register(self, plugin):
        """ 注册插件
        """
        if not isinstance(plugin, Plugin):
            raise Exception('Only support Plugin class')
        if plugin.name in self._plugin_list:
            raise Exception('Plugin name already registered.')
        self._plugin_list[plugin.name] = plugin
