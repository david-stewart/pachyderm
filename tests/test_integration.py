#!/usr/bin/env python

""" Test the integration between various classes.

"""

from io import StringIO
import logging
import numpy as np
import pytest  # noqa: F401
from typing import Any

from pachyderm import histogram
from pachyderm import yaml

logger = logging.getLogger(__name__)

def dump_to_string_and_retrieve(input_object: Any, y: yaml.ruamel.yaml.YAML = None) -> Any:
    """ Dump the given input object via YAML and then retrieve it for comparison.

    Args:
        input_object: Object to be dumped and retrieved.
        y: YAML object to use for the dumping. If not specified, one will be created.
    Returns:
        The dumped and then retrieved object.
    """
    # Create a YAML object if necessary
    if y is None:
        y = yaml.yaml()

    # Dump to a string
    s = StringIO()
    y.dump([input_object], s)
    s.seek(0)
    # And then load from the string. Note the implicit unpacking
    output_object, = y.load(s)

    return output_object

def test_Histogram1D_with_yaml(logging_mixin) -> None:
    """ Test writing and then reading a Histogram1D via YAML.

    This ensures that writing a histogram1D can be done successfully.
    """
    # Setup
    # YAML object
    y = yaml.yaml(classes_to_register = [histogram.Histogram1D])
    # Test hist
    input_hist = histogram.Histogram1D(
        bin_edges = np.linspace(0, 10, 11), y = np.linspace(2, 20, 10),
        errors_squared = np.linspace(2, 20, 10)
    )
    # Access "x" since it is generated but then stored in the class. This could disrupt YAML, so
    # we should explicitly test it.
    input_hist.x

    # Dump and load (ie round trip)
    output_hist = dump_to_string_and_retrieve(input_hist, y = y)

    # Check the result
    assert input_hist == output_hist

