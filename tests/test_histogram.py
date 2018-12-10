#!/usr/bin/env python

""" Tests for the utilities module.

.. codeauthor:: Raymond Ehlers <raymond.ehlers@cern.ch>, Yale University
"""

import logging
import numpy as np
import os
import pytest
import uproot

from pachyderm import histogram

# Setup logger
logger = logging.getLogger(__name__)

@pytest.fixture
def retrieve_root_list(testRootHists):
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
    # very well. Identical hists will be not equal in smoe cases...
    hists = []
    h = testRootHists.hist1D
    for i in range(3):
        hists.append(h.Clone("{}_{}".format(h.GetName(), i)))
    l1 = ROOT.TList()
    l1.SetName("mainList")
    l2 = ROOT.TList()
    l2.SetName("innerList")
    for h in hists:
        l1.Add(h)
        l2.Add(h)
    l1.Add(l2)

    # File for comparison.
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "testFiles", "testOpeningList.root")
    # Create the file if needed.
    if not os.path.exists(filename):
        current_directory = ROOT.TDirectory.CurrentDirectory()
        lCopy = l1.Clone("tempMainList")
        # The objects will be destroyed when l is written.
        # However, we write it under the l name to ensure it is read corectly later
        f = ROOT.TFile(filename, "RECREATE")
        f.cd()
        lCopy.Write(l1.GetName(), ROOT.TObject.kSingleKey)
        f.Close()
        current_directory.cd()

    # Create expected values
    # See the docstring for an explanation of the format.
    expected = {}
    innerDict = {}
    mainList = {}
    for h in hists:
        innerDict[h.GetName()] = h
        mainList[h.GetName()] = h
    mainList["innerList"] = innerDict
    expected["mainList"] = mainList

    yield (filename, l1, expected)

    # We need to call Clear() because we reference the same histograms in both the main list
    # the inner list. If we don't explicitly call it on the main list, it may be called on the
    # inner list first, which will then lead to the hists being undefined when Clear() is called
    # on the main list later.
    l1.Clear()

@pytest.mark.ROOT
class TestRetrievingHistgramsFromAList():
    def test_get_histograms_in_list(self, loggingMixin, retrieve_root_list):
        """ Test for retrieving a list of histograms from a ROOT file. """
        (filename, root_list, expected) = retrieve_root_list

        output = histogram.get_histograms_in_list(filename, "mainList")

        # The first level of the output is removed by `getHistogramsInList()`
        expected = expected["mainList"]

        # This isn't the most sophisticated way of comparsion, but bin-by-bin is sufficient for here.
        # We take advantage that we know the structure of the file so we don't need to handle recursion
        # or higher dimensional hists.
        outputInnerList = output.pop("innerList")
        expectedInnerList = expected.pop("innerList")
        for (o, e) in [(output, expected), (outputInnerList, expectedInnerList)]:
            for oHist, eHist in zip(o.values(), e.values()):
                oValues = [oHist.GetBinContent(i) for i in range(0, oHist.GetXaxis().GetNbins() + 2)]
                eValues = [eHist.GetBinContent(i) for i in range(0, eHist.GetXaxis().GetNbins() + 2)]
                assert np.allclose(oValues, eValues)

    def test_get_non_existent_list(self, loggingMixin, retrieve_root_list):
        """ Test for retrieving a list which doesn't exist from a ROOT file. """
        (filename, root_list, expected) = retrieve_root_list

        output = histogram.get_histograms_in_list(filename, "nonExistent")
        assert output is None

    def test_retrieve_object(self, loggingMixin, retrieve_root_list):
        """ Test for retrieving a list of histograms from a ROOT file.

        NOTE: One would normally expect to have the hists in the first level of the dict, but
              this is actually taken care of in `getHistogramsInList()`, so we need to avoid
              doing it in the tests here.
        """
        (filename, root_list, expected) = retrieve_root_list

        output = {}
        histogram._retrieve_object(output, root_list)

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
    expected = histogram.Histogram1D(x = np.arange(1, 11) - 0.5,
                                     y = np.array([0, 0, 0, 2, 0, 0, 0, 0, 3, 0]),
                                     errors_squared = np.array([0, 0, 0, 4, 0, 0, 0, 0, 3, 0]))

    histName = "rootHist"
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "testFiles", "convertHist.root")
    if not os.path.exists(filename):
        # Need to create the initial histogram.
        # This shouldn't happen very often, as the file is stored in the repository.
        import ROOT
        rootHist = ROOT.TH1F(histName, histName, 10, 0, 10)
        rootHist.Fill(3, 2)
        for _ in range(3):
            rootHist.Fill(8)

        # Write out with normal ROOT so we can avoid further dependencies
        fOut = ROOT.TFile(filename, "RECREATE")
        rootHist.Write()
        fOut.Close()

    return filename, histName, expected

def check_hist(input_hist: histogram.Histogram1D, expected: histogram.Histogram1D) -> bool:
    """ Helper function to compare a given Histogram against expected values.

    Args:
        input_hist (histogram.Histogram1D): Converted histogram.
        expected (histogram.Histogram1D): Expected hiostgram.
    Returns:
        bool: True if the histograms are the same.
    """
    if not isinstance(input_hist, histogram.Histogram1D):
        h = histogram.Histogram1D.from_existing_hist(input_hist)
    else:
        h = input_hist
    # Ensure that there are entries
    assert len(h.x) > 0
    # Then check the actual values
    np.testing.assert_allclose(h.x, expected.x)
    assert len(h.y) > 0
    np.testing.assert_allclose(h.y, expected.y)
    assert len(h.errors) > 0
    np.testing.assert_allclose(h.errors, expected.errors)

    return True

@pytest.mark.ROOT
def test_ROOT_hist_to_histogram(setup_histogram_conversion):
    """ Check conversion of a read in ROOT file via ROOT to a Histogram object. """
    filename, histName, expected = setup_histogram_conversion

    # Setup and read histogram
    import ROOT
    fIn = ROOT.TFile(filename, "READ")
    input_hist = fIn.Get(histName)

    assert check_hist(input_hist, expected) is True

    # Cleanup
    fIn.Close()

def test_uproot_hist_to_histogram(setup_histogram_conversion):
    """ Check conversion of a read in ROOT file via uproot to a Histogram object. """
    filename, histName, expected = setup_histogram_conversion

    # Retrieve the stored histogram via uproot
    uproot_file = uproot.open(filename)
    input_hist = uproot_file[histName]

    assert check_hist(input_hist, expected) is True

    # Cleanup
    del uproot_file

@pytest.mark.ROOT
class TestWithRootHists():
    def test_get_array_from_hist(self, loggingMixin, testRootHists):
        """ Test getting numpy arrays from a 1D hist.

        Note:
            This test is from the legacy get_array_from_hist(...) function. This functionality is
            superceded by Histogram1D.from_existing_hist(...), but we leave this test for good measure.
        """
        hist = testRootHists.hist1D
        hist_array = histogram.Histogram1D.from_existing_hist(hist)

        # Determine expected values
        xBins = range(1, hist.GetXaxis().GetNbins() + 1)
        expected_hist_array = histogram.Histogram1D(
            x = np.array([hist.GetXaxis().GetBinCenter(i) for i in xBins]),
            y = np.array([hist.GetBinContent(i) for i in xBins]),
            errors_squared = np.array([hist.GetBinError(i) for i in xBins])**2,
            #errors_squared = np.array(hist.GetSumw2()),
        )

        logger.debug(f"sumw2: {len(hist.GetSumw2())}")
        logger.debug(f"sumw2: {hist.GetSumw2N()}")
        #assert np.array_equal(hist_array.x, expected_hist_array.x)
        #assert np.array_equal(hist_array.y, expected_hist_array.y)
        assert check_hist(hist_array, expected_hist_array) is True
        #assert np.array_equal(hist_array.errors, expected_hist_array.errors)

    @pytest.mark.parametrize("set_zero_to_NaN", [
        False, True
    ], ids = ["Keep zeroes as zeroes", "Set zeroes to NaN"])
    def test_get_array_from_hist2D(self, loggingMixin, set_zero_to_NaN, testRootHists):
        """ Test getting numpy arrays from a 2D hist. """
        hist = testRootHists.hist2D
        hist_array = histogram.get_array_from_hist2D(hist = hist, set_zero_to_NaN = set_zero_to_NaN)

        # Determine expected values
        xRange = np.array([hist.GetXaxis().GetBinCenter(i) for i in range(1, hist.GetXaxis().GetNbins() + 1)])
        yRange = np.array([hist.GetYaxis().GetBinCenter(i) for i in range(1, hist.GetYaxis().GetNbins() + 1)])
        expectedX, expectedY = np.meshgrid(xRange, yRange)
        expectedHistArray = np.array([hist.GetBinContent(x, y) for x in range(1, hist.GetXaxis().GetNbins() + 1) for y in range(1, hist.GetYaxis().GetNbins() + 1)], dtype=np.float32).reshape(hist.GetXaxis().GetNbins(), hist.GetYaxis().GetNbins())
        if set_zero_to_NaN:
            expectedHistArray[expectedHistArray == 0] = np.nan

        assert np.array_equal(hist_array[0], expectedX)
        assert np.array_equal(hist_array[1], expectedY)
        # Need to use the special `np.testing.assert_array_equal()` to properly
        # handle comparing NaN in the array. It returns _None_ if it is successful,
        # so we compare against that. It will raise an exception if they disagree
        assert np.testing.assert_array_equal(hist_array[2], expectedHistArray) is None

