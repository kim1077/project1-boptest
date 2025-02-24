# -*- coding: utf-8 -*-
"""
This module contains testing utilities used throughout test scripts, including
common functions and partial classes.

"""

import os
import requests
import unittest
import numpy as np
import json
import pandas as pd
import re
import matplotlib.pyplot as plt


def get_root_path():
    '''Returns the path to the root repository directory.

    '''

    testing_path = os.path.dirname(os.path.realpath(__file__));
    root_path = os.path.split(testing_path)[0]

    return root_path;

def clean_up(dir_path):
    '''Cleans up the .fmu, .mo, .txt, .mat, .json files from directory.

    Parameters
    ----------
    dir_path : str
        Directory path to clean up

    '''

    files = os.listdir(dir_path)
    for f in files:
        if f.endswith('.fmu') or f.endswith('.mo') or f.endswith('.txt') or f.endswith('.mat') or f.endswith('.json'):
            os.remove(os.path.join(dir_path, f))

def run_tests(test_file_name):
    '''Run tests and save results for specified test file.

    Parameters
    ----------
    test_file_name : str
        Test file name (ends in .py)

    '''

    # Load tests
    test_loader = unittest.TestLoader()
    suite = test_loader.discover(os.path.join(get_root_path(),'testing'), pattern = test_file_name)
    num_cases = suite.countTestCases()
    # Run tests
    print('\nFound {0} tests to run in {1}.\n\nRunning...'.format(num_cases, test_file_name))
    result = unittest.TextTestRunner(verbosity = 1).run(suite);
    # Parse and save results
    num_failures = len(result.failures)
    num_errors = len(result.errors)
    num_passed = num_cases - num_errors - num_failures
    log_json = {'TestFile':test_file_name, 'NCases':num_cases, 'NPassed':num_passed, 'NErrors':num_errors, 'NFailures':num_failures, 'Failures':{}, 'Errors':{}}
    for i, failure in enumerate(result.failures):
        log_json['Failures'][i]= failure[1]
    for i, error in enumerate(result.errors):
        log_json['Errors'][i]= error[1]
    log_file = os.path.splitext(test_file_name)[0] + '.log'
    with open(os.path.join(get_root_path(),'testing',log_file), 'w') as f:
        json.dump(log_json, f)


def compare_references(vars_timeseries = ['reaTRoo_y'],
                       refs_old = 'multizone_residential_hydronic_old',
                       refs_new = 'multizone_residential_hydronic'):
    '''Method to perform visual inspection on how references have changed
    with respect to a previous version.

    Parameters
    ----------
    vars_timeseries : list
        List with strings indicating the variables to be plotted in time
        series graphs.
    refs_old : str
        Name of the folder containing the old references.
    refs_new : str
        Name of the folder containing the new references.

    '''

    dir_old = os.path.join(get_root_path(), 'testing', 'references', refs_old)

    for subdir, _, files in os.walk(dir_old):
        for filename in files:
            f_old = os.path.join(subdir, filename)
            f_new = os.path.join(subdir.replace(refs_old,refs_new), filename)
            if not os.path.exists(f_new):
                print('File: {} has not been compared since it does not exist anymore.'.format(f_new))

            elif not f_old.endswith('.csv'):
                print('File: {} has not been compared since it is not a csv file.'.format(f_old))

            else:
                df_old = pd.read_csv(f_old)
                df_new = pd.read_csv(f_new)

                if not('time' in df_old.columns or 'keys' in df_old.columns):
                    print('File: {} has not been compared because the format is not recognized.'.format(f_old))
                else:
                    if 'time' in df_old.columns:
                        df_old.drop('time', axis=1, inplace=True)
                        df_new.drop('time', axis=1, inplace=True)
                        kind = 'line'
                        vars_to_plot = vars_timeseries
                    elif 'keys' in df_old.columns:
                        df_old = df_old.set_index('keys')
                        df_new = df_new.set_index('keys')
                        kind = 'bar'
                        vars_to_plot = df_old.columns

                    if 'kpis_' in filename:
                        fig, axs = plt.subplots(nrows=1, ncols=len(df_old.index), figsize=(10,8))
                        for i,k in enumerate(df_old.index):
                            axs[i].bar(0, df_old.loc[k,'value'], label='old', alpha=0.5, color='orange')
                            axs[i].bar(0, df_new.loc[k,'value'], label='new', alpha=0.5, color='blue')
                            axs[i].set_title(k)
                        fig.suptitle(str(f_new))
                        plt.legend()
                    else:
                        if any([v in df_old.keys() for v in vars_to_plot]):
                            for v in vars_to_plot:
                                if v in df_old.keys():
                                    _, ax = plt.subplots(1, figsize=(10,8))
                                    df_old[v].plot(ax=ax, label='old '+v, kind=kind, alpha=0.5, color='orange')
                                    df_new[v].plot(ax=ax, label='new '+v, kind=kind, alpha=0.5, color='blue')
                                    ax.set_title(str(f_new))
                                    ax.legend()
                        else:
                            print('File: {} has not been compared because it does not contain any of the variables to plot'.format(f_old))

    plt.show()

class partialChecks(object):
    '''This partial class implements common ref data check methods.

    '''

    def compare_ref_timeseries_df(self, df, ref_filepath):
        '''Compare a timeseries dataframe to a reference csv.

        Parameters
        ----------
        df : pandas DataFrame
            Test dataframe with "time" as index.
        ref_filepath : str
            Reference file path relative to testing directory.

        Returns
        -------
        None

        '''

        # Check time is index
        assert(df.index.name == 'time')
        # Perform test
        if os.path.exists(ref_filepath):
            # If reference exists, check it
            df_ref = pd.read_csv(ref_filepath, index_col='time')
            # Check all keys in reference are in test
            for key in df_ref.columns.to_list():
                self.assertTrue(key in df.columns.to_list(), 'Reference key {0} not in test data.'.format(key))
            # Check all keys in test are in reference
            for key in df.columns.to_list():
                self.assertTrue(key in df_ref.columns.to_list(), 'Test key {0} not in reference data.'.format(key))
            # Check trajectories
            for key in df.columns:
                y_test = self.create_test_points(df[key]).to_numpy()
                y_ref = self.create_test_points(df_ref[key]).to_numpy()
                results = self.check_trajectory(y_test, y_ref)
                self.assertTrue(results['Pass'], '{0} Key is {1}.'.format(results['Message'],key))
        else:
            # Otherwise, save as reference
            df.to_csv(ref_filepath)

        return None

    def compare_ref_json(self, json_test, ref_filepath):
            '''Compare a json to a reference json saved as .json.

            Parameters
            ----------
            json_test : Dict
                Test json in the form of a dictionary.
            ref_filepath : str
                Reference .json file path relative to testing directory.

            Returns
            -------
            None

            '''

            # Perform test
            if os.path.exists(ref_filepath):
                # If reference exists, check it
                with open(ref_filepath, 'r') as f:
                    json_ref = json.load(f)
                self.assertTrue(json_test==json_ref, 'json_test:\n{0}\ndoes not equal\njson_ref:\n{1}'.format(json_test, json_ref))
            else:
                # Otherwise, save as reference
                with open(ref_filepath, 'w') as f:
                    json.dump(json_test,f)

            return None

    def compare_ref_values_df(self, df, ref_filepath):
        '''Compare a values dataframe to a reference csv.

        Parameters
        ----------
        df : pandas DataFrame
            Test dataframe with a number of keys as index paired with values.
        ref_filepath : str
            Reference file path relative to testing directory.

        Returns
        -------
        None

        '''

        # Check keys is index
        assert(df.index.name == 'keys')
        assert(df.columns.to_list() == ['value'])
        # Perform test
        if os.path.exists(ref_filepath):
            # If reference exists, check it
            df_ref = pd.read_csv(ref_filepath, index_col='keys')
            for key in df.index.values:
                y_test = [df.loc[key,'value']]
                y_ref = [df_ref.loc[key,'value']]
                results = self.check_trajectory(y_test, y_ref)
                self.assertTrue(results['Pass'], '{0} Key is {1}.'.format(results['Message'],key))
        else:
            # Otherwise, save as reference
            df.to_csv(ref_filepath)

        return None

    def check_trajectory(self, y_test, y_ref):
        '''Check a numeric trajectory against a reference with a tolerance.

        Parameters
        ----------
        y_test : list-like of numerics
            Test trajectory
        y_ref : list-like of numerics
            Reference trajectory

        Returns
        -------
        result : dict
            Dictionary of result of check.
            {'Pass' : bool, True if ErrorMax <= tol, False otherwise.
             'ErrorMax' : float or None, Maximum error, None if fail length check
             'IndexMax' : int or None, Index of maximum error,None if fail length check
             'Message' : str or None, Message if failed check, None if passed.
            }

        '''

        # Set tolerance
        tol = 1e-3
        # Initialize return dictionary
        result =  {'Pass' : True,
                   'ErrorMax' : None,
                   'IndexMax' : None,
                   'Message' : None}
        # First, check that trajectories are same length
        if len(y_test) != len(y_ref):
            result['Pass'] = False
            result['Message'] = 'Test and reference trajectory not the same length.'
        else:
            # Initialize error arrays
            err_abs = np.zeros(len(y_ref))
            err_rel = np.zeros(len(y_ref))
            err_fun = np.zeros(len(y_ref))
            # Calculate errors
            for i in range(len(y_ref)):
                # Absolute error
                err_abs[i] = np.absolute(y_test[i] - y_ref[i])
                # Relative error
                if (abs(y_ref[i]) > 10 * tol):
                    err_rel[i] = err_abs[i] / abs(y_ref[i])
                else:
                    err_rel[i] = 0
                # Total error
                err_fun[i] = err_abs[i] + err_rel[i]
                # Assess error
                err_max = max(err_fun);
                i_max = np.argmax(err_fun);
                if err_max > tol:
                    result['Pass'] = False
                    result['ErrorMax'] = err_max,
                    result['IndexMax'] = i_max,
                    result['Message'] = 'Max error ({0}) in trajectory greater than tolerance ({1}) at index {2}. y_test: {3}, y_ref:{4}'.format(err_max, tol, i_max, y_test[i_max], y_ref[i_max])

        return result

    def create_test_points(self, s,n=500):
        '''Create interpolated points to test of a certain number.

        Useful to reduce number of points to test and to avoid failed tests from
        event times being slightly different.

        Parameters
        ----------
        s : pandas Series
            Series containing test points to create, with index as time floats.
        n : int, optional
            Number of points to create
            Default is 500

        Returns
        -------
        s_test : pandas Series
            Series containing interpolated data

        '''

        # Get data
        data = s.to_numpy()
        index = s.index.values
        # Make interpolated index
        t_min = index.min()
        t_max = index.max()
        t = np.linspace(t_min, t_max, n)
        # Interpolate data
        data_interp = np.interp(t,index,data)
        # Use at most 8 significant digits
        data_interp = [ float('{:.8g}'.format(x)) for x in data_interp ]
        # Make Series
        s_test = pd.Series(data=data_interp, index=t)

        return s_test

    def results_to_df(self, points, start_time, final_time, url='http://127.0.0.1:5000'):
        '''Convert results from boptest into pandas DataFrame timeseries.

        Parameters
        ----------
        points: list of str
            List of points to retrieve from boptest api.
        start_time: float
            Starting time of data to get in seconds.
        final_time: float
            Ending time of data to get in seconds.
        url: str
            URL pointing to deployed boptest test case.
            Default is http://127.0.0.1:5000.

        Returns
        -------
        df: pandas DataFrame
            Timeseries dataframe object with "time" as index in seconds.

        '''

        df = pd.DataFrame()
        for point in points:
            res = requests.put('{0}/results'.format(url), data={'point_name':point,'start_time':start_time, 'final_time':final_time}).json()
            df = pd.concat((df,pd.DataFrame(data=res[point], index=res['time'],columns=[point])), axis=1)
        df.index.name = 'time'

        return df

    def get_all_points(self, url='localhost:5000'):
        '''Get all of the input and measurement point names from boptest.

        Parameters
        ----------
        url: str, optional
            URL pointing to deployed boptest test case.
            Default is localhost:5000.

        Returns
        -------
        points: list of str
            List of available point names.

        '''

        measurements = requests.get('{0}/measurements'.format(url)).json()
        inputs = requests.get('{0}/inputs'.format(url)).json()
        points = list(measurements.keys()) + list(inputs.keys())

        return points


class partialTestAPI(partialChecks):
    '''This partial class implements common API tests for test cases.

    References to self attributes for the tests should be set in the setUp
    method of the particular testclass test.  They are:

    url : str
        URL to deployed testcase.
    name : str
        Name given to test
    inputs_ref : list of str
        List of names of inputs
    measurements_ref : list of str
        List of names of measurements
    step_ref : numeric
        Default simulation step

    '''

    def test_get_version(self):
        '''Test getting the version of BOPTEST.

        '''

        # Get version from BOPTEST API
        version = requests.get('{0}/version'.format(self.url)).json()
        # Create a regex object as three decimal digits seperated by period
        r_num = re.compile('\d.\d.\d')
        r_x = re.compile('0.x.x')
        # Test that the returned version matches the expected string format
        if r_num.match(version['version']) or r_x.match(version['version']):
            self.assertTrue(True)
        else:
            self.assertTrue(False, '/version did not return correctly. Returned {0}.'.format(version))

    def test_get_name(self):
        '''Test getting the name of test.

        '''

        name = requests.get('{0}/name'.format(self.url)).json()
        self.assertEqual(name['name'], self.name)

    def test_get_inputs(self):
        '''Test getting the input list of tests.

        '''

        inputs = requests.get('{0}/inputs'.format(self.url)).json()
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'get_inputs.json')
        self.compare_ref_json(inputs, ref_filepath)

    def test_get_measurements(self):
        '''Test getting the measurement list of test.

        '''

        measurements = requests.get('{0}/measurements'.format(self.url)).json()
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'get_measurements.json')
        self.compare_ref_json(measurements, ref_filepath)

    def test_get_step(self):
        '''Test getting the communication step of test.

        '''

        step = requests.get('{0}/step'.format(self.url)).json()
        df = pd.DataFrame(data=[step], index=['step'], columns=['value'])
        df.index.name = 'keys'
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'get_step.csv')
        self.compare_ref_values_df(df, ref_filepath)

    def test_set_step(self):
        '''Test setting the communication step of test.

        '''

        step_current = requests.get('{0}/step'.format(self.url)).json()
        step = 101
        requests.put('{0}/step'.format(self.url), data={'step':step})
        step_set = requests.get('{0}/step'.format(self.url)).json()
        self.assertEqual(step, step_set)
        requests.put('{0}/step'.format(self.url), data={'step':step_current})

    def test_initialize(self):
        '''Test initialization of test simulation.

        '''

        # Get measurements and inputs
        points = self.get_all_points(self.url)
        # Get current step
        step = requests.get('{0}/step'.format(self.url)).json()
        # Initialize
        start_time = 0.5*24*3600
        y = requests.put('{0}/initialize'.format(self.url), data={'start_time':start_time, 'warmup_period':0.5*24*3600}).json()
        # Check that initialize returns the right initial values and results
        df = pd.DataFrame.from_dict(y, orient = 'index', columns=['value'])
        df.index.name = 'keys'
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'initial_values.csv')
        self.compare_ref_values_df(df, ref_filepath)
        # Check trajectories
        df = self.results_to_df(points, 0, start_time, self.url)
        # Set reference file path
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'results_initialize_initial.csv')
        # Check results
        self.compare_ref_timeseries_df(df,ref_filepath)
        # Check kpis
        res_kpi = requests.get('{0}/kpi'.format(self.url)).json()
        df = pd.DataFrame.from_dict(res_kpi, orient='index', columns=['value'])
        df.index.name = 'keys'
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'kpis_initialize_initial.csv')
        self.compare_ref_values_df(df, ref_filepath)
        # Advance
        step_advance = 1*24*3600
        requests.put('{0}/step'.format(self.url), data={'step':step_advance})
        y = requests.post('{0}/advance'.format(self.url),data = {}).json()
        # Check trajectories
        df = self.results_to_df(points, start_time, start_time+step_advance, self.url)
        # Set reference file path
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'results_initialize_advance.csv')
        # Check results
        self.compare_ref_timeseries_df(df,ref_filepath)
        # Check kpis
        res_kpi = requests.get('{0}/kpi'.format(self.url)).json()
        df = pd.DataFrame.from_dict(res_kpi, orient='index', columns=['value'])
        df.index.name = 'keys'
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'kpis_initialize_advance.csv')
        self.compare_ref_values_df(df, ref_filepath)
        # Set step back to step
        requests.put('{0}/step'.format(self.url), data={'step':step})

    def test_advance_no_data(self):
        '''Test advancing of simulation with no input data.

        This is a basic test of functionality.
        Tests for advancing with overwriting are done in the example tests.

        '''

        requests.put('{0}/initialize'.format(self.url), data={'start_time':0, 'warmup_period':0})
        requests.put('{0}/step'.format(self.url), data={'step':self.step_ref})
        y = requests.post('{0}/advance'.format(self.url), data=dict()).json()
        df = pd.DataFrame.from_dict(y, orient = 'index', columns=['value'])
        df.index.name = 'keys'
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'advance_no_data.csv')
        self.compare_ref_values_df(df, ref_filepath)

    def test_advance_false_overwrite(self):
        '''Test advancing of simulation with overwriting as false.

        This is a basic test of functionality.
        Tests for advancing with overwriting are done in the example tests.

        '''

        if self.name == 'testcase1':
            u = {'oveAct_activate':0, 'oveAct_u':1500}
        elif self.name == 'testcase2':
            u = {'oveTSetRooHea_activate':0, 'oveTSetRooHea_u':273.15+22}
        elif self.name == 'testcase3':
            u = {'oveActNor_activate':0, 'oveActNor_u':1500,
                 'oveActSou_activate':0, 'oveActSou_u':1500}
        elif self.name == 'bestest_air':
            u = {'fcu_oveTSup_activate':0, 'fcu_oveTSup_u':290}
        elif self.name == 'bestest_hydronic':
            u = {'oveTSetSup_activate':0, 'oveTSetSup_u':273.15+60,
                 'ovePum_activate':0, 'ovePum_u':1}
        elif self.name == 'bestest_hydronic_heat_pump':
            u = {'oveTSet_activate':0, 'oveTSet_u':273.15+22}
        elif self.name == 'multizone_residential_hydronic':
            u = {'conHeaRo1_oveTSetHea_activate':0, 'conHeaRo1_oveTSetHea_u':273.15+22,
                 'oveEmiPum_activate':0, 'oveEmiPum_u':1}
        requests.put('{0}/initialize'.format(self.url), data={'start_time':0, 'warmup_period':0})
        requests.put('{0}/step'.format(self.url), data={'step':self.step_ref})
        y = requests.post('{0}/advance'.format(self.url), data=u).json()
        df = pd.DataFrame.from_dict(y, orient = 'index', columns=['value'])
        df.index.name = 'keys'
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'advance_false_overwrite.csv')
        self.compare_ref_values_df(df, ref_filepath)

    def test_get_forecast_default(self):
        '''Check that the forecaster is able to retrieve the data.

        Default forecast parameters for testcase used.

        '''

        # Initialize
        requests.put('{0}/initialize'.format(self.url), data={'start_time':0, 'warmup_period':0})
        # Test case forecast
        forecast = requests.get('{0}/forecast'.format(self.url)).json()
        df_forecaster = pd.DataFrame(forecast).set_index('time')
        # Set reference file path
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'get_forecast_default.csv')
        # Check the forecast
        self.compare_ref_timeseries_df(df_forecaster, ref_filepath)

    def test_put_and_get_parameters(self):
        '''Check PUT and GET of forecast settings.

        '''

        # Define forecast parameters
        forecast_parameters_ref = {'horizon':3600, 'interval':300}
        # Set forecast parameters
        ret = requests.put('{0}/forecast_parameters'.format(self.url),
                           data=forecast_parameters_ref)
        # Get forecast parameters
        forecast_parameters = requests.get('{0}/forecast_parameters'.format(self.url)).json()
        # Check the forecast parameters
        self.assertDictEqual(forecast_parameters, forecast_parameters_ref)
        # Check the return on the put request
        self.assertDictEqual(ret.json(), forecast_parameters_ref)

    def test_get_forecast_with_parameters(self):
        '''Check that the forecaster is able to retrieve the data.

        Custom forecast parameters used.

        '''

        # Define forecast parameters
        forecast_parameters_ref = {'horizon':3600, 'interval':300}
        # Initialize
        requests.put('{0}/initialize'.format(self.url), data={'start_time':0, 'warmup_period':0})
        # Set forecast parameters
        requests.put('{0}/forecast_parameters'.format(self.url),
                     data=forecast_parameters_ref)
        # Test case forecast
        forecast = requests.get('{0}/forecast'.format(self.url)).json()
        df_forecaster = pd.DataFrame(forecast).set_index('time')
        # Set reference file path
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'get_forecast_with_parameters.csv')
        # Check the forecast
        self.compare_ref_timeseries_df(df_forecaster, ref_filepath)

    def test_set_get_scenario(self):
        '''Test setting and getting the scenario of test.

        '''

        # Set scenario
        scenario_current = requests.get('{0}/scenario'.format(self.url)).json()
        scenario = {'electricity_price':'highly_dynamic',
                    'time_period':self.test_time_period}
        requests.put('{0}/scenario'.format(self.url), data=scenario)
        scenario_set = requests.get('{0}/scenario'.format(self.url)).json()
        self.assertEqual(scenario, scenario_set)
        # Check initialized correctly
        measurements = requests.get('{0}/measurements'.format(self.url)).json()
        # Don't check weather
        points_check = []
        for key in measurements.keys():
            if 'weaSta' not in key:
                points_check.append(key)
        df = self.results_to_df(points_check, -np.inf, np.inf, self.url)
        # Set reference file path
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'results_set_scenario.csv')
        # Check results
        self.compare_ref_timeseries_df(df,ref_filepath)
        # Return scenario to original
        requests.put('{0}/scenario'.format(self.url), data=scenario_current)


    def test_partial_results_inner(self):
        '''Test getting results for start time after and final time before.

        '''

        requests.put('{0}/initialize'.format(self.url), data={'start_time':0, 'warmup_period':0})
        requests.put('{0}/step'.format(self.url), data={'step':self.step_ref})
        measurements = requests.get('{0}/measurements'.format(self.url)).json()
        requests.post('{0}/advance'.format(self.url), data=dict()).json()
        res_inner = requests.put('{0}/results'.format(self.url), data={'point_name':list(measurements.keys())[0], \
                                                                 'start_time':self.step_ref*0.25, \
                                                                 'final_time':self.step_ref*0.75}).json()
        df = pd.DataFrame.from_dict(res_inner).set_index('time')
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'partial_results_inner.csv')
        self.compare_ref_timeseries_df(df, ref_filepath)

    def test_partial_results_outer(self):
        '''Test getting results for start time before and final time after.

        '''

        requests.put('{0}/initialize'.format(self.url), data={'start_time':0, 'warmup_period':0})
        requests.put('{0}/step'.format(self.url), data={'step':self.step_ref})
        measurements = requests.get('{0}/measurements'.format(self.url)).json()
        requests.post('{0}/advance'.format(self.url), data=dict()).json()
        res_outer = requests.put('{0}/results'.format(self.url), data={'point_name':list(measurements.keys())[0], \
                                                                 'start_time':0-self.step_ref, \
                                                                 'final_time':self.step_ref*2}).json()
        df = pd.DataFrame.from_dict(res_outer).set_index('time')
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'partial_results_outer.csv')
        self.compare_ref_timeseries_df(df, ref_filepath)

class partialTestTimePeriod(partialChecks):
    '''Partial class for testing the time periods for each test case

    '''

    def run_time_period(self, time_period):
        '''Runs the example and tests the kpi and trajectory results for time period.

        Parameters
        ----------
        time_period: str
            Name of test_period to run

        Returns
        -------
        None

        '''

        # Set time period scenario
        requests.put('{0}/scenario'.format(self.url), data={'time_period':time_period})
        # Simulation Loop
        y = 1
        while y:
            # Advance simulation
            y = requests.post('{0}/advance'.format(self.url), data={}).json()
        # Check results
        df = self.results_to_df(self.points_check, -np.inf, np.inf, self.url)
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'results_{0}.csv'.format(time_period))
        self.compare_ref_timeseries_df(df,ref_filepath)
        # For each price scenario
        for price_scenario in ['constant', 'dynamic', 'highly_dynamic']:
            # Set scenario
            requests.put('{0}/scenario'.format(self.url), data={'electricity_price':price_scenario})
            # Report kpis
            res_kpi = requests.get('{0}/kpi'.format(self.url)).json()
            # Check kpis
            df = pd.DataFrame.from_dict(res_kpi, orient='index', columns=['value'])
            df.index.name = 'keys'
            ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'kpis_{0}_{1}.csv'.format(time_period, price_scenario))
            self.compare_ref_values_df(df, ref_filepath)
        requests.put('{0}/scenario'.format(self.url), data={'electricity_price':'constant'})

class partialTestSeason(partialChecks):
    '''Partial class for testing the time periods for each test case

    '''

    def run_season(self, season):
        '''Runs the example and tests the kpi and trajectory results for a season.

        Parameters
        ----------
        season: str
            Name of season to run.
            'winter' or 'summer' or 'shoulder'

        Returns
        -------
        None

        '''

        if season == 'winter':
            start_time = 1*24*3600
        elif season == 'summer':
            start_time = 248*24*3600
        elif season == 'shoulder':
            start_time = 118*24*3600
        else:
            raise ValueError('Season {0} unknown.'.format(season))
        length = 48*3600
        # Initialize test case
        requests.put('{0}/initialize'.format(self.url), data={'start_time':start_time, 'warmup_period':0})
        # Get default simulation step
        step_def = requests.get('{0}/step'.format(self.url)).json()
        # Simulation Loop
        for i in range(int(length/step_def)):
            # Advance simulation
            requests.post('{0}/advance'.format(self.url), data={}).json()
        requests.put('{0}/scenario'.format(self.url), data={'electricity_price':'constant'})
        # Check results
        points = self.get_all_points(self.url)
        df = self.results_to_df(points, start_time, start_time+length, self.url)
        ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'results_{0}.csv'.format(season))
        self.compare_ref_timeseries_df(df,ref_filepath)
        # For each price scenario
        for price_scenario in ['constant', 'dynamic', 'highly_dynamic']:
            # Set scenario
            requests.put('{0}/scenario'.format(self.url), data={'electricity_price':price_scenario})
            # Report kpis
            res_kpi = requests.get('{0}/kpi'.format(self.url)).json()
            # Check kpis
            df = pd.DataFrame.from_dict(res_kpi, orient='index', columns=['value'])
            df.index.name = 'keys'
            ref_filepath = os.path.join(get_root_path(), 'testing', 'references', self.name, 'kpis_{0}_{1}.csv'.format(season, price_scenario))
            self.compare_ref_values_df(df, ref_filepath)
