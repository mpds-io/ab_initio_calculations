import configparser
import os


class Settings:
    def __init__(self, config_path="ab_initio_calculations/conf/conf.ini"):
        self.config = configparser.ConfigParser()
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found at {config_path}")
        self.config.read(config_path)

        self.debug = self.config.getboolean("DEFAULT", "debug", fallback=False)
        self.log_level = self.config.get("DEFAULT", "log_level", fallback="INFO")

        self.basis_sets_dir = self.config.get("paths", "basis_sets_dir")
        self.pcrystal_input_dir = self.config.get("paths", "pcrystal_input_dir")

