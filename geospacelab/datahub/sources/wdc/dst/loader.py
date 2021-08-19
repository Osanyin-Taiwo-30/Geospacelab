import netCDF4
import numpy as np
import cftime
import datetime


class Loader:
    def __init__(self, file_path, file_type='nc', load_data=True):
        self.file_path = file_path
        self.file_type = file_type
        self.variables = {}
        self.done = False
        if load_data:
            self.load()

    def load(self):
        fnc = netCDF4.Dataset(self.file_path)
        variables = {}
        for var_name, var_name_nc in cdf_variable_name_dict.items():
            variables[var_name] = np.array(fnc[var_name_nc]).reshape((fnc[var_name_nc].shape[0], 1))

        time_units = fnc['UNIX_TIME'].units

        variables['DATETIME'] = cftime.num2date(variables['UNIX_TIME'].flatten(),
                                                units=time_units,
                                                only_use_cftime_datetimes=False,
                                                only_use_python_datetimes=True)

        variables['DATETIME'] = np.reshape(variables['DATETIME'], (fnc['UNIX_TIME'].shape[0], 1))
        self.variables = variables
        self.done = True
        fnc.close()


cdf_variable_name_dict = {
    'UNIX_TIME':    'UNIX_TIME',
    'Dst': 'Dst'
}
