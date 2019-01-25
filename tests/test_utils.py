#!/usr/bin/env python

""" Tests for the utilities module.

.. codeauthor:: Raymond Ehlers <raymond.ehlers@cern.ch>, Yale University
"""

import logging
import numpy as np
import pytest

from pachyderm import histogram
from pachyderm import utils

# Setup logger
logger = logging.getLogger(__name__)

@pytest.mark.parametrize("inputs, expected", [
    ((3, np.array([1, 2, 3, 4, 5, 4, 3, 2, 1])),
        np.array([6, 9, 12, 13, 12, 9, 6])),
    ((4, np.array([1, 2, 3, 4, 5, 4, 3, 2, 1])),
        np.array([10, 14, 16, 16, 14, 10])),
    ((3, np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])),
        np.array([6, 9, 12, 15, 18, 21, 24, 27])),
    ((3, np.array([10, 9, 8, 7, 6, 5, 4, 3, 2, 1])),
        np.array([27, 24, 21, 18, 15, 12, 9, 6]))
], ids = ["n = 3 trianglur values", "n = 4 triangular values", "n = 3 increasing values", "n = 3 decreasing values"])
def test_moving_average(logging_mixin, inputs, expected):
    """ Test the moving average calculation. """
    (n, arr) = inputs
    expected = expected / n
    assert np.array_equal(utils.moving_average(arr = arr, n = n), expected)

@pytest.mark.parametrize("path, expected", [
    ("standard_attr", "standard_attr_value"),
    ("attr1.attr3.my_attr", "recursive_attr_value"),
], ids = ["Standard attribute", "Recursive attribute"])
def test_recursive_getattr(logging_mixin, mocker, path, expected):
    """ Tests for recursive getattr. """
    # Setup mock objects from which we will recursively grab attributes
    mock_obj1 = mocker.MagicMock(spec = ["standard_attr", "attr1"])
    mock_obj2 = mocker.MagicMock(spec = ["attr3"])
    mock_obj3 = mocker.MagicMock(spec = ["my_attr"])
    mock_obj1.standard_attr = "standard_attr_value"
    mock_obj1.attr1 = mock_obj2
    mock_obj2.attr3 = mock_obj3
    mock_obj3.my_attr = "recursive_attr_value"

    # For convenience
    obj = mock_obj1
    # Check the returned value
    assert expected == utils.recursive_getattr(obj, path)

def test_recursive_getattr_defualt_value(logging_mixin, mocker):
    """ Test for retrieving a default value with getattr. """
    obj = mocker.MagicMock(spec = ["sole_attr"])
    assert "default_value" == utils.recursive_getattr(obj, "nonexistent_attr", "default_value")

def test_recursive_getattr_fail(logging_mixin, mocker):
    """ Test for failure of recursive getattr.

    It will fail the same was as the standard getattr.
    """
    obj = mocker.MagicMock(spec = ["sole_attr"])

    with pytest.raises(AttributeError) as exception_info:
        utils.recursive_getattr(obj, "nonexistent_attr")
    assert "nonexistent_attr" in exception_info.value.args[0]

@pytest.mark.ROOT
class TestWithRootHists():
    def test_get_array_for_fit(self, logging_mixin, mocker, test_root_hists):
        """ Test getting an array from a hist in a dict of observables. """
        observables = {}
        for i in range(5):
            observables[i] = mocker.MagicMock(spec = ["jet_pt_bin", "track_pt_bin", "hist"],
                                              jet_pt_bin = i, track_pt_bin = i + 2,
                                              hist = None)
        # We mock the Observable containing a HistogramContainer, which then contains a normal histogram.
        # We only want one Observable to work. All others shouldn't have a hist to ensure that the test
        # will fail if something has gone awry.
        observables[3].hist = mocker.MagicMock(spec = ["hist"], hist = test_root_hists.hist1D)
        hist_array = utils.get_array_for_fit(observables, jet_pt_bin = 3, track_pt_bin = 5)

        # Expected values
        expected_hist_array = histogram.Histogram1D.from_existing_hist(hist = test_root_hists.hist1D)

        # This is basically a copy of test_histogram.check_hist, but since it is brief and convenient
        # to have it here, we just leave it.
        assert len(hist_array.x) > 0
        assert np.array_equal(hist_array.x, expected_hist_array.x)
        assert len(hist_array.y) > 0
        assert np.array_equal(hist_array.y, expected_hist_array.y)
        assert len(hist_array.errors) > 0
        assert np.array_equal(hist_array.errors, expected_hist_array.errors)

