#!/usr/bin/env python

""" Tests for the utilities module.

.. codeauthor:: Raymond Ehlers <raymond.ehlers@cern.ch>, Yale University
"""

from dataclasses import dataclass
import logging
import numpy as np
import os
import pytest
import uproot

from pachyderm import histogram
from pachyderm.typing_helpers import Hist

# Setup logger
logger = logging.getLogger(__name__)

@pytest.fixture
def retrieve_root_list(test_root_hists):
    """ Create an set of lists to load for a ROOT file.

    NOTE: Not using a mock since I'd like to the real objects and storing
          a ROOT file is just as easy here.

    The expected should look like:
    ```
    {'mainList': OrderedDict([('test', Hist('test_1')),
                             ('test2', Hist('test_2')),
                             ('test3', Hist('test_3')),
                             ('innerList',
                              OrderedDict([('test', Hist('test_1')),
                                           ('test', Hist('test_2')),
                                           ('test', Hist('test_3'))]))])}
    ```
    """
    import ROOT

    # Create values for the test
    # We only use 1D hists so we can do the comparison effectively.
    # This is difficult because root hists don't handle operator==
    # very well. Identical hists will be not equal in some cases...
    hists = []
    h = test_root_hists.hist1D
    for i in range(3):
        hists.append(h.Clone("{}_{}".format(h.GetName(), i)))
    l1 = ROOT.TList()
    l1.SetName("mainList")
    l2 = ROOT.TList()
    l2.SetName("innerList")
    l3 = ROOT.TList()
    l3.SetName("secondList")
    for h in hists:
        l1.Add(h)
        l2.Add(h)
        l3.Add(h)
    l1.Add(l2)

    # File for comparison.
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "testFiles", "testOpeningList.root")
    # Create the file if needed.
    if not os.path.exists(filename):
        current_directory = ROOT.TDirectory.CurrentDirectory()
        lCopy = l1.Clone("mainList")
        lSecondCopy = l3.Clone("secondList")
        # The objects will be destroyed when l is written.
        # However, we write it under the l name to ensure it is read correctly later
        f = ROOT.TFile(filename, "RECREATE")
        f.cd()
        lCopy.Write(l1.GetName(), ROOT.TObject.kSingleKey)
        lSecondCopy.Write(l3.GetName(), ROOT.TObject.kSingleKey)
        f.Close()
        current_directory.cd()

    # Create expected values
    # See the docstring for an explanation of the format.
    expected = {}
    inner_dict = {}
    main_list = {}
    second_list = {}
    for h in hists:
        inner_dict[h.GetName()] = h
        main_list[h.GetName()] = h
        second_list[h.GetName()] = h
    main_list["innerList"] = inner_dict
    expected["mainList"] = main_list
    expected["secondList"] = second_list

    yield (filename, l1, expected)

    # We need to call Clear() because we reference the same histograms in both the main list
    # the inner list. If we don't explicitly call it on the main list, it may be called on the
    # inner list first, which will then lead to the hists being undefined when Clear() is called
    # on the main list later.
    l1.Clear()

@pytest.mark.ROOT
class TestOpenRootFile:
    def test_open_file(self, logging_mixin, retrieve_root_list):
        """ Test for context manager for opening ROOT files. """
        filename, root_list, expected = retrieve_root_list

        output = {}
        with histogram.RootOpen(filename = filename) as f:
            for name in ["mainList", "secondList"]:
                histogram._retrieve_object(output, f.Get(name))

        logger.debug(f"{output}")

        # This isn't the most sophisticated way of comparison, but bin-by-bin is sufficient for here.
        # We take advantage that we know the structure of the file so we don't need to handle recursion
        # or higher dimensional hists.
        output_inner_list = output["mainList"].pop("innerList")
        expected_inner_list = expected["mainList"].pop("innerList")
        output_second_list = output.pop("secondList")
        expected_second_list = expected.pop("secondList")
        for (o, e) in [(output["mainList"], expected["mainList"]), (output_inner_list, expected_inner_list), (output_second_list, expected_second_list)]:
            for oHist, eHist in zip(o.values(), e.values()):
                logger.info(f"oHist: {oHist}, eHist: {eHist}")
                oValues = [oHist.GetBinContent(i) for i in range(0, oHist.GetXaxis().GetNbins() + 2)]
                eValues = [eHist.GetBinContent(i) for i in range(0, eHist.GetXaxis().GetNbins() + 2)]
                assert np.allclose(oValues, eValues)

    def test_failing_to_open_file(self, logging_mixin):
        """ Test for raising the proper exception for a file that doesn't exist. """
        fake_filename = "fake_filename.root"
        with pytest.raises(IOError) as exception_info:
            with histogram.RootOpen(filename = fake_filename):
                pass
        # Check that the right exception was thrown by proxy via the filename.
        assert "Failed" in exception_info.value.args[0] and f"{fake_filename}" in exception_info.value.args[0]

@pytest.mark.ROOT
class TestRetrievingHistgramsFromAList:
    def test_get_histograms_in_file(self, logging_mixin, retrieve_root_list):
        """ Test for retrieving all of the histograms in a ROOT file. """
        (filename, root_list, expected) = retrieve_root_list

        output = histogram.get_histograms_in_file(filename = filename)
        logger.info(f"{output}")

        # This isn't the most sophisticated way of comparison, but bin-by-bin is sufficient for here.
        # We take advantage that we know the structure of the file so we don't need to handle recursion
        # or higher dimensional hists.
        output_inner_list = output["mainList"].pop("innerList")
        expected_inner_list = expected["mainList"].pop("innerList")
        output_second_list = output.pop("secondList")
        expected_second_list = expected.pop("secondList")
        for (o, e) in [(output["mainList"], expected["mainList"]), (output_inner_list, expected_inner_list), (output_second_list, expected_second_list)]:
            for oHist, eHist in zip(o.values(), e.values()):
                logger.info(f"oHist: {oHist}, eHist: {eHist}")
                oValues = [oHist.GetBinContent(i) for i in range(0, oHist.GetXaxis().GetNbins() + 2)]
                eValues = [eHist.GetBinContent(i) for i in range(0, eHist.GetXaxis().GetNbins() + 2)]
                assert np.allclose(oValues, eValues)

    def test_get_histograms_in_list(self, logging_mixin, retrieve_root_list):
        """ Test for retrieving a list of histograms from a ROOT file. """
        (filename, root_list, expected) = retrieve_root_list

        output = histogram.get_histograms_in_list(filename, "mainList")

        # The first level of the output is removed by `get_histograms_in_list()`
        expected = expected["mainList"]

        # This isn't the most sophisticated way of comparison, but bin-by-bin is sufficient for here.
        # We take advantage that we know the structure of the file so we don't need to handle recursion
        # or higher dimensional hists.
        output_inner_list = output.pop("innerList")
        expected_inner_list = expected.pop("innerList")
        for (o, e) in [(output, expected), (output_inner_list, expected_inner_list)]:
            for oHist, eHist in zip(o.values(), e.values()):
                oValues = [oHist.GetBinContent(i) for i in range(0, oHist.GetXaxis().GetNbins() + 2)]
                eValues = [eHist.GetBinContent(i) for i in range(0, eHist.GetXaxis().GetNbins() + 2)]
                assert np.allclose(oValues, eValues)

    def test_get_non_existent_list(self, logging_mixin, retrieve_root_list):
        """ Test for retrieving a list which doesn't exist from a ROOT file. """
        (filename, root_list, expected) = retrieve_root_list

        with pytest.raises(ValueError) as exception_info:
            histogram.get_histograms_in_list(filename, "nonExistent")
        assert "nonExistent" in exception_info.value.args[0]

    def test_retrieve_object(self, logging_mixin, retrieve_root_list):
        """ Test for retrieving a list of histograms from a ROOT file.

        NOTE: One would normally expect to have the hists in the first level of the dict, but
              this is actually taken care of in `get_histograms_in_list()`, so we need to avoid
              doing it in the tests here.
        """
        (filename, root_list, expected) = retrieve_root_list

        # Did we actually get histograms? Used when debugging ROOT memory issues that seem to occur after
        # an exception is raised...
        logger.debug(f"{root_list}, {expected}")

        output = {}
        histogram._retrieve_object(output, root_list)

        # Ignore second list
        expected.pop("secondList")

        assert output == expected

@pytest.fixture
def setup_histogram_conversion():
    """ Setup expected values for histogram conversion tests.

    This set of expected values corresponds to:

    >>> hist = ROOT.TH1F("test", "test", 10, 0, 10)
    >>> hist.Fill(3, 2)
    >>> hist.Fill(8)
    >>> hist.Fill(8)
    >>> hist.Fill(8)

    Note:
        The error on bin 9 (one-indexed) is just sqrt(counts), while the error on bin 4
        is sqrt(4) because we filled it with weight 2 (sumw2 squares this values).
    """
    expected = histogram.Histogram1D(bin_edges = np.linspace(0, 10, 11),
                                     y = np.array([0, 0, 0, 2, 0, 0, 0, 0, 3, 0]),
                                     errors_squared = np.array([0, 0, 0, 4, 0, 0, 0, 0, 3, 0]))

    hist_name = "rootHist"
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "testFiles", "convertHist.root")
    if not os.path.exists(filename):
        # Need to create the initial histogram.
        # This shouldn't happen very often, as the file is stored in the repository.
        import ROOT
        root_hist = ROOT.TH1F(hist_name, hist_name, 10, 0, 10)
        root_hist.Fill(3, 2)
        for _ in range(3):
            root_hist.Fill(8)

        # Write out with normal ROOT so we can avoid further dependencies
        fOut = ROOT.TFile(filename, "RECREATE")
        root_hist.Write()
        fOut.Close()

    return filename, hist_name, expected

def check_hist(input_hist: histogram.Histogram1D, expected: histogram.Histogram1D) -> bool:
    """ Helper function to compare a given Histogram against expected values.

    Args:
        input_hist (histogram.Histogram1D): Converted histogram.
        expected (histogram.Histogram1D): Expected histogram.
    Returns:
        bool: True if the histograms are the same.
    """
    if not isinstance(input_hist, histogram.Histogram1D):
        h = histogram.Histogram1D.from_existing_hist(input_hist)
    else:
        h = input_hist
    # Ensure that there are entries
    assert len(h.bin_edges) > 0
    # Then check the actual values
    np.testing.assert_allclose(h.bin_edges, expected.bin_edges)
    assert len(h.x) > 0
    np.testing.assert_allclose(h.x, expected.x)
    assert len(h.y) > 0
    np.testing.assert_allclose(h.y, expected.y)
    assert len(h.errors) > 0
    np.testing.assert_allclose(h.errors, expected.errors)

    return True

@pytest.mark.ROOT
def test_ROOT_hist_to_histogram(setup_histogram_conversion):
    """ Check conversion of a read in ROOT file via ROOT to a Histogram object. """
    filename, hist_name, expected = setup_histogram_conversion

    # Setup and read histogram
    import ROOT
    fIn = ROOT.TFile(filename, "READ")
    input_hist = fIn.Get(hist_name)

    assert check_hist(input_hist, expected) is True

    # Cleanup
    fIn.Close()

def test_uproot_hist_to_histogram(setup_histogram_conversion):
    """ Check conversion of a read in ROOT file via uproot to a Histogram object. """
    filename, hist_name, expected = setup_histogram_conversion

    # Retrieve the stored histogram via uproot
    uproot_file = uproot.open(filename)
    input_hist = uproot_file[hist_name]

    assert check_hist(input_hist, expected) is True

    # Cleanup
    del uproot_file

@pytest.mark.ROOT
class TestWithRootHists:
    def test_get_array_from_hist(self, logging_mixin, test_root_hists):
        """ Test getting numpy arrays from a 1D hist.

        Note:
            This test is from the legacy get_array_from_hist(...) function. This functionality is
            superseded by Histogram1D.from_existing_hist(...), but we leave this test for good measure.
        """
        hist = test_root_hists.hist1D
        hist_array = histogram.Histogram1D.from_existing_hist(hist)

        # Determine expected values
        x_bins = range(1, hist.GetXaxis().GetNbins() + 1)
        expected_bin_edges = np.empty(len(x_bins) + 1)
        expected_bin_edges[:-1] = [hist.GetXaxis().GetBinLowEdge(i) for i in x_bins]
        expected_bin_edges[-1] = hist.GetXaxis().GetBinUpEdge(hist.GetXaxis().GetNbins())
        expected_hist_array = histogram.Histogram1D(
            bin_edges = expected_bin_edges,
            y = np.array([hist.GetBinContent(i) for i in x_bins]),
            errors_squared = np.array([hist.GetBinError(i) for i in x_bins])**2,
        )

        logger.debug(f"sumw2: {len(hist.GetSumw2())}")
        logger.debug(f"sumw2: {hist.GetSumw2N()}")
        assert check_hist(hist_array, expected_hist_array) is True

    def test_non_uniform_binning(self, logging_mixin, setup_non_uniform_binning):
        """ Test non-uniform binning in Histogram1D. """
        hist = setup_non_uniform_binning

        # Determine expected values.
        x_bins = range(1, hist.GetXaxis().GetNbins() + 1)
        expected_bin_edges = np.empty(len(x_bins) + 1)
        expected_bin_edges[:-1] = [hist.GetXaxis().GetBinLowEdge(i) for i in x_bins]
        expected_bin_edges[-1] = hist.GetXaxis().GetBinUpEdge(hist.GetXaxis().GetNbins())

        expected_hist = histogram.Histogram1D.from_existing_hist(hist)

        # The naming is a bit confusing here, but basically we want to compare the
        # non-uniform binning in a ROOT hist vs a Histogram1D. We also then extract the bin
        # edges here as an extra cross-check.
        assert np.allclose(expected_hist.bin_edges, expected_bin_edges)
        # Check the calculated bin widths
        assert np.allclose(expected_hist.bin_widths, expected_bin_edges[1:] - expected_bin_edges[:-1])
        # Then we check all of the fields to be safe.
        # (This is a bit redundant because both objects will use Histogram1D, but it doesn't hurt).
        assert check_hist(hist, expected_hist)

        # This uses uniform binning and it _shouldn't_ agree.
        uniform_bins = np.linspace(expected_bin_edges[0], expected_bin_edges[-1], hist.GetXaxis().GetNbins() + 1)
        logger.info(f"expected_bin_edges: {expected_bin_edges}")
        logger.info(f"uniform_bins: {uniform_bins}")
        assert not np.allclose(expected_hist.bin_edges, uniform_bins)

    @pytest.mark.parametrize("use_bin_edges", [
        False, True
    ], ids = ["Use bin centers", "Use bin edges"])
    @pytest.mark.parametrize("set_zero_to_NaN", [
        False, True
    ], ids = ["Keep zeroes as zeroes", "Set zeroes to NaN"])
    def test_get_array_from_hist2D(self, logging_mixin, use_bin_edges, set_zero_to_NaN, test_root_hists):
        """ Test getting numpy arrays from a 2D hist. """
        hist = test_root_hists.hist2D
        x, y, hist_array = histogram.get_array_from_hist2D(hist = hist, set_zero_to_NaN = set_zero_to_NaN, return_bin_edges = use_bin_edges)

        # Determine expected values
        if use_bin_edges:
            epsilon = 1e-9
            x_bin_edges = np.empty(hist.GetXaxis().GetNbins() + 1)
            x_bin_edges[:-1] = [hist.GetXaxis().GetBinLowEdge(i) for i in range(1, hist.GetXaxis().GetNbins() + 1)]
            x_bin_edges[-1] = hist.GetXaxis().GetBinUpEdge(hist.GetXaxis().GetNbins())
            y_bin_edges = np.empty(hist.GetYaxis().GetNbins() + 1)
            y_bin_edges[:-1] = [hist.GetYaxis().GetBinLowEdge(i) for i in range(1, hist.GetYaxis().GetNbins() + 1)]
            y_bin_edges[-1] = hist.GetYaxis().GetBinUpEdge(hist.GetYaxis().GetNbins())
            x_mesh = np.arange(np.amin(x_bin_edges), np.amax(x_bin_edges) + epsilon, hist.GetXaxis().GetBinWidth(1))
            y_mesh = np.arange(np.amin(y_bin_edges), np.amax(y_bin_edges) + epsilon, hist.GetYaxis().GetBinWidth(1))
        else:
            x_mesh = np.array([hist.GetXaxis().GetBinCenter(i) for i in range(1, hist.GetXaxis().GetNbins() + 1)])
            y_mesh = np.array([hist.GetYaxis().GetBinCenter(i) for i in range(1, hist.GetYaxis().GetNbins() + 1)])
        x_range = x_mesh
        y_range = y_mesh
        expected_x, expected_y = np.meshgrid(x_range, y_range)
        expected_hist_array = np.array([
            hist.GetBinContent(x, y)
            for x in range(1, hist.GetXaxis().GetNbins() + 1)
            for y in range(1, hist.GetYaxis().GetNbins() + 1)], dtype=np.float32
        ).reshape(hist.GetYaxis().GetNbins(), hist.GetXaxis().GetNbins())
        if set_zero_to_NaN:
            expected_hist_array[expected_hist_array == 0] = np.nan

        assert np.allclose(x, expected_x)
        assert np.allclose(y, expected_y)
        assert np.allclose(hist_array, expected_hist_array, equal_nan = True)

        # Check particular values for good measure.
        assert np.isclose(hist_array[1][0], 1.0)
        if set_zero_to_NaN:
            assert np.isnan(hist_array[0][1])
        else:
            assert np.isclose(hist_array[0][1], 0.0)

@pytest.fixture
def setup_basic_hist(logging_mixin):
    """ Setup a basic `Histogram1D` for basic tests.

    This histogram contains 4 bins, with edges of [0, 1, 2, 3, 5], values of [2, 2, 3, 0], with
    errors of [4, 2, 3, 0], simulating the first bin being filled once with a weight of 2, and the
    rest being filled normally. It could be reproduced in ROOT with:

    >>> bins = np.array([0, 1, 2, 3, 5], dtype = np.float64)
    >>> hist = ROOT.TH1F("test", "test", 4, binning)
    >>> hist.Fill(0, 2)
    >>> hist.Fill(1)
    >>> hist.Fill(1)
    >>> hist.Fill(2)
    >>> hist.Fill(2)
    >>> hist.Fill(2)

    Args:
        None.
    Returns:
        hist, bin_edges, y, errors_squared
    """
    bin_edges = np.array([0, 1, 2, 3, 5])
    y = np.array([2, 2, 3, 0])
    # As if the first bin was filled with weight of 2.
    errors_squared = np.array([4, 2, 3, 0])

    h = histogram.Histogram1D(bin_edges = bin_edges, y = y, errors_squared = errors_squared)

    return h, bin_edges, y, errors_squared

@pytest.mark.parametrize("value, expected_bin", [
    (0, 0),
    (0.5, 0),
    (1, 1),
    (1.0, 1),
    (1.5, 1),
    (1.99, 1),
    (2, 2),
    (3, 3),
    (4.5, 3),
], ids = ["start bin 0", "mid bin 0",
          "start bin 1", "float start bin 1", "mid bin 1", "end bin 1",
          "bin 2",
          "bin 3", "upper bin 3"])
def test_find_bin(logging_mixin, setup_basic_hist, value, expected_bin):
    """ Test for finding the bin based on a given value. """
    h, _, _, _ = setup_basic_hist
    found_bin = h.find_bin(value)

    assert found_bin == expected_bin

@pytest.mark.parametrize("test_equality", [
    False,
    True,
], ids = ["Test inequality", "Test equality"])
@pytest.mark.parametrize("access_attributes_which_are_stored", [
    False,
    True,
], ids = ["Do not access other attributes", "Access other attributes which are stored"])
def test_histogram1D_equality(logging_mixin, setup_basic_hist, test_equality, access_attributes_which_are_stored):
    """ Test for Histogram1D equality. """
    h, bin_edges, y, errors_squared = setup_basic_hist

    h1 = histogram.Histogram1D(bin_edges = bin_edges, y = y, errors_squared = errors_squared)
    h2 = histogram.Histogram1D(bin_edges = bin_edges, y = y, errors_squared = errors_squared)

    if access_attributes_which_are_stored:
        # This attribute will be stored (but under "_x"), so we want to make sure that it
        # doesn't disrupt the equality comparison.
        h1.x

    if not test_equality:
        h1.bin_edges = np.array([5, 6, 7, 8, 9])

    if test_equality:
        assert h1 == h2
    else:
        assert h1 != h2

@dataclass
class HistInfo:
    """ Convenience for storing hist testing information.

    Could reuse the ``Histogram1D`` object, but since we're testing it here, it seems better to use
    a separate object.
    """
    y: np.array
    errors_squared: np.array

    def convert_to_histogram_1D(self, bin_edges: np.array) -> histogram.Histogram1D:
        """ Convert these stored values into a ``Histogram1D``. """
        return histogram.Histogram1D(
            bin_edges = bin_edges,
            y = self.y,
            errors_squared = self.errors_squared,
        )

    def convert_to_ROOT_hist(self, bin_edges: np.array) -> Hist:
        """ Convert these stored values in a ROOT.TH1F.

        This isn't very robust, which is why I'm not including it in ``Histogram1D``. However,
        something simple is sufficient for our purposes here.
        """
        import ROOT
        hist = ROOT.TH1F("tempHist", "tempHist", len(bin_edges) - 1, bin_edges.astype(float))
        hist.Sumw2()

        # Exclude under- and overflow
        for i, (val, error_squared) in enumerate(zip(self.y, self.errors_squared), start = 1):
            # ROOT hists are 1-indexed.
            hist.SetBinContent(i, val)
            hist.SetBinError(i, np.sqrt(error_squared))

        return hist

class TestHistogramOperators:
    """ Test ``Histogram1D`` operators.

    In principle, we could refactor all of the tests by explicitly calling
    the functions. But since the expected values are different for each test,
    and the test code itself is very simple, there doesn't seem to be much point.
    """
    _bin_edges = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    _filled_two_times = HistInfo(np.array([0, 0, 2., 0, 0, 0, 0, 0, 0, 0]),
                                 np.array([0, 0, 2., 0, 0, 0, 0, 0, 0, 0]))
    _filled_four_times = HistInfo(np.array([0, 0, 4., 0, 0, 0, 0, 0, 0, 0]),
                                  np.array([0, 0, 4., 0, 0, 0, 0, 0, 0, 0]))
    _filled_once_with_weight_of_2 = HistInfo(np.array([0, 0, 2., 0, 0, 0, 0, 0, 0, 0]),
                                             np.array([0, 0, 4., 0, 0, 0, 0, 0, 0, 0]))
    _filled_twice_with_weight_of_2 = HistInfo(np.array([0, 0, 4., 0, 0, 0, 0, 0, 0, 0]),
                                              np.array([0, 0, 8., 0, 0, 0, 0, 0, 0, 0]))

    @pytest.fixture(params = [
        (_filled_two_times, _filled_four_times,
            HistInfo(np.array([0, 0, 6, 0, 0, 0, 0, 0, 0, 0]), np.array([0, 0, 6, 0, 0, 0, 0, 0, 0, 0]))),
        (_filled_two_times, _filled_twice_with_weight_of_2,
            HistInfo(np.array([0, 0, 6, 0, 0, 0, 0, 0, 0, 0]), np.array([0, 0, 10, 0, 0, 0, 0, 0, 0, 0]))),
        (_filled_once_with_weight_of_2, _filled_twice_with_weight_of_2,
            HistInfo(np.array([0, 0, 6, 0, 0, 0, 0, 0, 0, 0]), np.array([0, 0, 12, 0, 0, 0, 0, 0, 0, 0]))),
    ], ids = ["Standard filled", "One standard, one weighted", "Two weighted"])
    def setup_addition(self, request, logging_mixin):
        """ We want to share this parametrization between multiple tests, so we define it as a fixture.

        However, each test performs rather different steps, so there is little else to do here.
        """
        # Setup
        h1 = request.param[0].convert_to_histogram_1D(bin_edges = self._bin_edges)
        h2 = request.param[1].convert_to_histogram_1D(bin_edges = self._bin_edges)
        return (*request.param, h1, h2)

    def test_addition(self, setup_addition):
        """ Test addition in ``Histogram1D``. """
        # Setup
        h1_info, h2_info, expected, h1, h2 = setup_addition

        # Operation
        h3 = h1 + h2

        # Check result
        assert np.allclose(h3.bin_edges, self._bin_edges)
        assert np.allclose(h3.y, expected.y)
        assert np.allclose(h3.errors_squared, expected.errors_squared)

    @pytest.mark.ROOT
    def test_compare_addition_to_ROOT(self, setup_addition):
        """ Compare the result of ``Histogram1D`` addition vs ROOT. """
        # Setup
        h1_info, h2_info, expected, h1, h2 = setup_addition
        h1_root = h1_info.convert_to_ROOT_hist(bin_edges = self._bin_edges)
        h2_root = h2_info.convert_to_ROOT_hist(bin_edges = self._bin_edges)

        # Operation
        h3 = h1 + h2
        h1_root.Add(h2_root)

        # Check result
        assert check_hist(h1_root, h3)

    def test_sum_function(self, setup_addition):
        """ Test addition using sum(...) with ``Histogram1D``. """
        # Setup
        h1_info, h2_info, expected, h1, h2 = setup_addition

        # Operation
        h3 = sum([h1, h2])

        # Check result
        assert np.allclose(h3.bin_edges, self._bin_edges)
        assert np.allclose(h3.y, expected.y)
        assert np.allclose(h3.errors_squared, expected.errors_squared)

    @pytest.fixture(params = [
        (_filled_two_times, _filled_four_times,
            HistInfo(np.array([0, 0, 2, 0, 0, 0, 0, 0, 0, 0]), np.array([0, 0, 6, 0, 0, 0, 0, 0, 0, 0]))),
        (_filled_two_times, _filled_twice_with_weight_of_2,
            HistInfo(np.array([0, 0, 2, 0, 0, 0, 0, 0, 0, 0]), np.array([0, 0, 10, 0, 0, 0, 0, 0, 0, 0]))),
        (_filled_once_with_weight_of_2, _filled_twice_with_weight_of_2,
            HistInfo(np.array([0, 0, 2, 0, 0, 0, 0, 0, 0, 0]), np.array([0, 0, 12, 0, 0, 0, 0, 0, 0, 0]))),
    ], ids = ["Standard filled", "One standard, one weighted", "Two weighted"])
    def setup_subtraction(self, request, logging_mixin):
        """ We want to share this parametrization between multiple tests, so we define it as a fixture.

        However, each test performs rather different steps, so there is little else to do here.
        """
        # Setup
        h1 = request.param[0].convert_to_histogram_1D(bin_edges = self._bin_edges)
        h2 = request.param[1].convert_to_histogram_1D(bin_edges = self._bin_edges)
        return (*request.param, h1, h2)

    def test_subtraction(self, setup_subtraction):
        """ Test subtraction. """
        # Setup
        h1_info, h2_info, expected, h1, h2 = setup_subtraction

        # Operation
        h3 = h2 - h1

        # Check result
        assert np.allclose(h3.bin_edges, self._bin_edges)
        assert np.allclose(h3.y, expected.y)
        assert np.allclose(h3.errors_squared, expected.errors_squared)

    @pytest.mark.ROOT
    def test_compare_subtraction_to_ROOT(self, setup_subtraction):
        """ Compare the result of ``Histogram1D`` subtraction vs ROOT. """
        # Setup
        h1_info, h2_info, expected, h1, h2 = setup_subtraction
        h1_root = h1_info.convert_to_ROOT_hist(bin_edges = self._bin_edges)
        h2_root = h2_info.convert_to_ROOT_hist(bin_edges = self._bin_edges)

        # Operation
        h3 = h2 - h1
        h2_root.Add(h1_root, -1)

        # Check result
        assert check_hist(h2_root, h3)

    @pytest.fixture(params = [
        (_filled_two_times, _filled_four_times,
            HistInfo(np.array([0, 0, 8, 0, 0, 0, 0, 0, 0, 0]), np.array([0, 0, 48, 0, 0, 0, 0, 0, 0, 0]))),
        (_filled_two_times, _filled_twice_with_weight_of_2,
            HistInfo(np.array([0, 0, 8, 0, 0, 0, 0, 0, 0, 0]), np.array([0, 0, 64, 0, 0, 0, 0, 0, 0, 0]))),
        (_filled_once_with_weight_of_2, _filled_twice_with_weight_of_2,
            HistInfo(np.array([0, 0, 8, 0, 0, 0, 0, 0, 0, 0]), np.array([0, 0, 96, 0, 0, 0, 0, 0, 0, 0]))),
    ], ids = ["Standard filled", "One standard, one weighted", "Two weighted"])
    def setup_multiplication(self, request, logging_mixin):
        """ We want to share this parametrization between multiple tests, so we define it as a fixture.

        However, each test performs rather different steps, so there is little else to do here.
        """
        # Setup
        h1 = request.param[0].convert_to_histogram_1D(bin_edges = self._bin_edges)
        h2 = request.param[1].convert_to_histogram_1D(bin_edges = self._bin_edges)
        return (*request.param, h1, h2)

    def test_multiplication(self, setup_multiplication):
        """ Test multiplication. """
        # Setup
        h1_info, h2_info, expected, h1, h2 = setup_multiplication

        # Operation
        h3 = h2 * h1

        # Check result
        assert np.allclose(h3.bin_edges, self._bin_edges)
        assert np.allclose(h3.y, expected.y)
        assert np.allclose(h3.errors_squared, expected.errors_squared)

    @pytest.mark.ROOT
    def test_compare_multiplication_to_ROOT(self, setup_multiplication):
        """ Compare the result of ``Histogram1D`` multiplication vs ROOT. """
        # Setup
        h1_info, h2_info, expected, h1, h2 = setup_multiplication
        h1_root = h1_info.convert_to_ROOT_hist(bin_edges = self._bin_edges)
        h2_root = h2_info.convert_to_ROOT_hist(bin_edges = self._bin_edges)

        # Operation
        h3 = h2 * h1
        h2_root.Multiply(h1_root)

        # Check result
        assert check_hist(h2_root, h3)

    @pytest.fixture(params = [
        (_filled_two_times, _filled_four_times,
            HistInfo(np.array([0, 0, 2, 0, 0, 0, 0, 0, 0, 0]), np.array([0, 0, 3, 0, 0, 0, 0, 0, 0, 0]))),
        (_filled_two_times, _filled_twice_with_weight_of_2,
            HistInfo(np.array([0, 0, 2, 0, 0, 0, 0, 0, 0, 0]), np.array([0, 0, 4, 0, 0, 0, 0, 0, 0, 0]))),
        (_filled_once_with_weight_of_2, _filled_twice_with_weight_of_2,
            HistInfo(np.array([0, 0, 2, 0, 0, 0, 0, 0, 0, 0]), np.array([0, 0, 6, 0, 0, 0, 0, 0, 0, 0]))),
    ], ids = ["Standard filled", "One standard, one weighted", "Two weighted"])
    def setup_division(self, request, logging_mixin):
        """ We want to share this parametrization between multiple tests, so we define it as a fixture.

        However, each test performs rather different steps, so there is little else to do here.
        """
        # Setup
        h1 = request.param[0].convert_to_histogram_1D(bin_edges = self._bin_edges)
        h2 = request.param[1].convert_to_histogram_1D(bin_edges = self._bin_edges)
        return (*request.param, h1, h2)

    def test_division(self, setup_division):
        """ Test division. """
        # Setup
        h1_info, h2_info, expected, h1, h2 = setup_division

        # Operation
        h3 = h2 / h1

        # Check result
        assert np.allclose(h3.bin_edges, self._bin_edges)
        assert np.allclose(h3.y, expected.y)
        assert np.allclose(h3.errors_squared, expected.errors_squared)

    @pytest.mark.ROOT
    def test_compare_division_to_ROOT(self, setup_division):
        """ Compare the result of ``Histogram1D`` division vs ROOT. """
        # Setup
        h1_info, h2_info, expected, h1, h2 = setup_division
        h1_root = h1_info.convert_to_ROOT_hist(bin_edges = self._bin_edges)
        h2_root = h2_info.convert_to_ROOT_hist(bin_edges = self._bin_edges)

        # Operation
        h3 = h2 / h1
        h2_root.Divide(h1_root)

        # Check result
        assert check_hist(h2_root, h3)

@pytest.mark.ROOT
class TestIntegrateHistogram1D:
    """ Test for counting and integrating bins stored in a ``Histogram1D``.

    These tests require ROOT because we compare against ROOT to check that the values
    are correct.
    """
    @pytest.fixture(params = [
        (0, 3, False),  # Specified in the form of the 0-indexed `Histogram1D` bins.
        (1.2, 4.3, True),
    ], ids = ["Bins", "Values"])
    def setup_hists_and_args(self, request, logging_mixin):
        """ Setup hist for testing integration.

        Note:
            The `Histogram1D` bins are 0-indexed, while the ROOT bins are 1-indexed.
        """
        # Setup
        min_arg, max_arg, using_values = request.param
        import ROOT
        bins = np.array([1, 2, 3, 4, 6], dtype = np.float64)
        values = np.array([5, 6, 7, 8])

        h_root = ROOT.TH1F("test", "test", 4, bins)
        h_root.Sumw2()
        for b, i in zip(bins, values):
            for _ in range(i):
                h_root.Fill(b)
        # Ensure that we test with weighting too.
        h_root.Fill(4.5, 4)
        # And correspondingly increase the values (in case we decide to use them at some other time).
        values[3] += 4

        h = histogram.Histogram1D.from_existing_hist(h_root)

        # Setup args
        args = {}
        if using_values:
            root_min_arg = h_root.GetXaxis().FindBin(min_arg)
            root_max_arg = h_root.GetXaxis().FindBin(max_arg)
            args = {
                "min_value": min_arg,
                "max_value": max_arg,
            }
        else:
            # Need the + 1 to convert from 0-indexed to 1-indexed bins.
            root_min_arg = min_arg + 1
            root_max_arg = max_arg + 1
            args = {
                "min_bin": min_arg,
                "max_bin": max_arg,
            }

        return args, h, root_min_arg, root_max_arg, h_root

    def test_integrate(self, setup_hists_and_args):
        """ Test integration of bins. """
        # Setup
        import ROOT
        args, h, root_min_arg, root_max_arg, h_root = setup_hists_and_args

        # Integrate
        expected_error = ROOT.Double(0)
        expected_result = h_root.IntegralAndError(root_min_arg, root_max_arg, expected_error, "width")
        res, res_error = h.integral(**args)

        # Check result
        assert np.isclose(res, expected_result)
        assert np.isclose(res_error, expected_error)

    def test_counts_in_interval(self, setup_hists_and_args):
        """ Test the counting of values stored within bins in an interval. """
        # Setup
        import ROOT
        args, h, root_min_arg, root_max_arg, h_root = setup_hists_and_args

        # Count
        expected_error = ROOT.Double(0)
        expected_result = h_root.IntegralAndError(root_min_arg, root_max_arg, expected_error, "")
        res, res_error = h.counts_in_interval(**args)

        # Check result
        assert np.isclose(res, expected_result)
        assert np.isclose(res_error, expected_error)

    def test_integral_validation_for_mixed_bins_and_values(self, setup_hists_and_args):
        """ Test mixed arguments of bins and values. """
        # Setup
        import ROOT
        args, h, root_min_arg, root_max_arg, h_root = setup_hists_and_args

        # Mix the arguments so  that we pass "min_bin" with "max_value" or "min_value" with "max_bin"
        if "min_value" in args:
            args["min_bin"] = h.find_bin(args.pop("min_value"))
        else:
            args["min_value"] = h.bin_edges[args.pop("min_bin")]

        # Integrate
        expected_error = ROOT.Double(0)
        expected_result = h_root.IntegralAndError(root_min_arg, root_max_arg, expected_error, "width")
        res, res_error = h.integral(**args)

        # Check result
        assert np.isclose(res, expected_result)
        assert np.isclose(res_error, expected_error)

class TestHistogramIntegralValidation:
    """ Tests histogram integral validation. These tests don't require ROOT, so they are separate. """
    def test_integral_validation_for_min_values(self, setup_basic_hist):
        """ Should fail when passed both min value and min bin. """
        # Setup
        h, _, _, _ = setup_basic_hist

        with pytest.raises(ValueError) as exception_info:
            h.integral(min_value = 3, min_bin = 4)
        assert "Only specify one" in exception_info.value.args[0]

    def test_integral_validation_for_max_values(self, setup_basic_hist):
        """ Should fail when passed both max value and max bin. """
        # Setup
        h, _, _, _ = setup_basic_hist

        with pytest.raises(ValueError) as exception_info:
            h.integral(max_value = 3, max_bin = 4)
        assert "Only specify one" in exception_info.value.args[0]

    def test_integral_validation_for_inverted_values(self, setup_basic_hist):
        """ Should fail when min > max. """
        # Setup
        h, _, _, _ = setup_basic_hist

        with pytest.raises(ValueError) as exception_info:
            h.integral(min_value = 3, max_value = 1)
        assert "greater than" in exception_info.value.args[0]
