# Licensed under the BSD 3-Clause License
# Copyright (C) 2021 GeospaceLab (geospacelab)
# Author: Lei Cai, Space Physics and Astronomy, University of Oulu

import numpy as np
import datetime

import geospacelab.datahub as datahub
from geospacelab.datahub import DatabaseModel, FacilityModel, InstrumentModel, ProductModel
from geospacelab.datahub.sources.esa_eo import esaeo_database
from geospacelab.datahub.sources.esa_eo.swarm import swarm_facility
from geospacelab import preferences as prf
import geospacelab.toolbox.utilities.pybasic as basic
import geospacelab.toolbox.utilities.pylogging as mylog
import geospacelab.toolbox.utilities.pydatetime as dttool
from geospacelab.datahub.sources.esa_eo.swarm.advanced.efi_lp_hm.loader import Loader as default_Loader
from geospacelab.datahub.sources.esa_eo.swarm.advanced.efi_lp_hm.downloader import Downloader as default_Downloader
import geospacelab.datahub.sources.esa_eo.swarm.advanced.efi_lp_hm.variable_config as var_config


default_dataset_attrs = {
    'database': esaeo_database,
    'facility': swarm_facility,
    'instrument': 'EFI-LP',
    'product': 'LP_HM',
    'data_file_ext': 'cdf',
    'product_version': 'latest',
    'data_root_dir': prf.datahub_data_root_dir / 'ESA' / 'SWARM' / 'Advanced',
    'allow_load': True,
    'allow_download': True,
    'force_download': False,
    'data_search_recursive': False,
    'quality_control': False,
    'calib_control': False,
    'label_fields': ['database', 'facility', 'instrument', 'product'],
    'load_mode': 'AUTO',
    'time_clip': True,
}

default_variable_names = [
    'SC_DATETIME',
    'SC_GEO_LAT',
    'SC_GEO_LON',
    'SC_GEO_ALT',
    'SC_GEO_r',
    'SC_SZA',
    'SC_SAz',
    'SC_ST',
    'SC_DIP_LAT',
    'SC_DIP_LON',
    'SC_QD_MLT',
    'SC_QD_LAT',
    'SC_AACGM_LAT',
    'SC_AACGM_LON',
    'n_e',
    'T_e_HGN',
    'T_e_LGN',
    'T_e',
    'V_s_HGN',
    'V_s_LGN',
    'SC_U',
    'QUALITY_FLAG'
    ]

# default_data_search_recursive = True

default_attrs_required = []


class Dataset(datahub.DatasetSourced):
    def __init__(self, **kwargs):
        kwargs = basic.dict_set_default(kwargs, **default_dataset_attrs)

        super().__init__(**kwargs)

        self.database = kwargs.pop('database', 'ESA/EarthOnline')
        self.facility = kwargs.pop('facility', 'SWARM')
        self.instrument = kwargs.pop('instrument', 'EFI-LP')
        self.product = kwargs.pop('product', 'HM02')
        self.product_version = kwargs.pop('product', '')
        self.local_latest_version = ''
        self.allow_download = kwargs.pop('allow_download', False)
        self.force_download = kwargs.pop('force_download', False)
        self.quality_control = kwargs.pop('quality_control', False)
        self.calib_control = kwargs.pop('calib_control', False)
        self._data_root_dir = self.data_root_dir    # Record the initial root dir

        self.sat_id = kwargs.pop('sat_id', 'A')

        self.metadata = None

        allow_load = kwargs.pop('allow_load', False)

        # self.config(**kwargs)

        if self.loader is None:
            self.loader = default_Loader

        if self.downloader is None:
            self.downloader = default_Downloader

        self._validate_attrs()

        if allow_load:
            self.load_data()

    def _validate_attrs(self):
        for attr_name in default_attrs_required:
            attr = getattr(self, attr_name)
            if not list(attr):
                mylog.StreamLogger.warning("The parameter {} is required before loading data!".format(attr_name))

        self.data_root_dir = self.data_root_dir / self.instrument / self.product

        if str(self.product_version) and self.product_version != 'latest':
            self.data_root_dir = self._data_root_dir / self.product_version
        else:
            self.product_version = 'latest'
            try:
                dirs_product_version = [f.name for f in self._data_root_dir.iterdir() if f.is_dir()]
            except FileNotFoundError:
                dirs_product_version = []
                self.force_download = True
            else:
                if not list(dirs_product_version):
                    self.force_download = True

            if list(dirs_product_version):
                self.local_latest_version = max(dirs_product_version)
                self.data_root_dir = self._data_root_dir / self.local_latest_version
                if not self.force_download:
                    mylog.simpleinfo.info(
                        "Note: Loading the local files " +
                        "with the latest version {} ".format(self.local_latest_version) +
                        "Keep an eye on the latest baselines online!"
                    )

    def label(self, **kwargs):
        label = super().label()
        return label

    def load_data(self, **kwargs):
        self.check_data_files(**kwargs)

        self._set_default_variables(
            default_variable_names,
            configured_variables=var_config.configured_variables
        )
        for file_path in self.data_file_paths:
            load_obj = self.loader(file_path, file_type='cdf')

            for var_name in self._variables.keys():
                value = load_obj.variables[var_name]
                self._variables[var_name].join(value)

            # self.select_beams(field_aligned=True)
        if self.time_clip:
            self.time_filter_by_range(var_datetime_name='SC_DATETIME')
        if self.quality_control:
            self.time_filter_by_quality()
        if self.calib_control:
            self.time_filter_by_calib()

    def time_filter_by_quality(self, quality_flags=None):
        if quality_flags is None:
            quality_flags = np.array([1])

        for qf in quality_flags:
            inds = np.where(self['QUALITY_FLAG'].value.flatten() == qf)[0]
            for key in self.keys():
                self._variables[key].value = self._variables[key].value[inds, ::]

    def time_filter_by_calib(self, calib_flags=None):

        if calib_flags is None:
            calib_flags = np.array([0])

        for cf in calib_flags:
            inds = np.where(self['CALIB_FLAG'].value.flatten() == cf)[0]
            for key in self.keys():
                self._variables[key].value = self._variables[key].value[inds, ::]

    def search_data_files(self, **kwargs):

        dt_fr = self.dt_fr
        dt_to = self.dt_to

        diff_days = dttool.get_diff_days(dt_fr, dt_to)

        dt0 = dttool.get_start_of_the_day(dt_fr)

        for i in range(diff_days + 1):
            this_day = dt0 + datetime.timedelta(days=i)

            initial_file_dir = kwargs.pop(
                'initial_file_dir', self.data_root_dir
            )

            file_patterns = [
                'EFI' + self.sat_id.upper(),
                self.product.upper(),
                this_day.strftime('%Y%m%d') + 'T',
            ]
            # remove empty str
            file_patterns = [pattern for pattern in file_patterns if str(pattern)]
            search_pattern = '*' + '*'.join(file_patterns) + '*'

            done = super().search_data_files(
                initial_file_dir=initial_file_dir,
                search_pattern=search_pattern,
                allow_multiple_files=True,
            )
            # Validate file paths

            if (not done and self.allow_download) or self.force_download:
                done = self.download_data()
                if done:
                    self._validate_attrs()
                    initial_file_dir = self.data_root_dir
                    done = super().search_data_files(
                        initial_file_dir=initial_file_dir,
                        search_pattern=search_pattern,
                        allow_multiple_files=True
                    )

        return done

    def download_data(self, dt_fr=None, dt_to=None):
        if dt_fr is None:
            dt_fr = self.dt_fr
        if dt_to is None:
            dt_to = self.dt_to
        download_obj = self.downloader(
            dt_fr, dt_to,
            sat_id=self.sat_id,
            data_type=self.product,
            file_version=self.product_version,
            force=self.force_download
        )
        if download_obj.done:
            self.force_download = False

            if download_obj.file_version != self.local_latest_version and self.product_version == 'latest':
                mylog.StreamLogger.warning(
                    f"A newer version of data files have been downloaded ({download_obj.file_version})"
                )
            self.product_version = download_obj.file_version
            self.data_root_dir = self._data_root_dir
            self._validate_attrs()

        return download_obj.done

    @property
    def database(self):
        return self._database

    @database.setter
    def database(self, value):
        if isinstance(value, str):
            self._database = DatabaseModel(value)
        elif issubclass(value.__class__, DatabaseModel):
            self._database = value
        else:
            raise TypeError

    @property
    def product(self):
        return self._product

    @product.setter
    def product(self, value):
        if isinstance(value, str):
            self._product = ProductModel(value)
        elif issubclass(value.__class__, ProductModel):
            self._product = value
        else:
            raise TypeError

    @property
    def facility(self):
        return self._facility

    @facility.setter
    def facility(self, value):
        if isinstance(value, str):
            self._facility = FacilityModel(value)
        elif issubclass(value.__class__, FacilityModel):
            self._facility = value
        else:
            raise TypeError

    @property
    def instrument(self):
        return self._instrument

    @instrument.setter
    def instrument(self, value):
        if isinstance(value, str):
            self._instrument = InstrumentModel(value)
        elif issubclass(value.__class__, InstrumentModel):
            self._instrument = value
        else:
            raise TypeError