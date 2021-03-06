# Dockerfile for testing pachyderm
# NOTE: This could also be used for running pachyderm, but it wouldn't be terribly useful.
# We use the Overwatch base image so we don't have to deal with setting up ROOT.
# All we need to know is that the user is named "overwatch".
# Set the python version here so that we can use it to set the base image.
ARG PYTHON_VERSION=3.7.1
FROM rehlers/overwatch-base:py${PYTHON_VERSION}
LABEL maintainer="Raymond Ehlers <raymond.ehlers@cern.ch>, Yale University"

# Setup environment
ENV ROOTSYS="/opt/root"
ENV PATH="${ROOTSYS}/bin:/home/overwatch/.local/bin:${PATH}"
ENV LD_LIBRARY_PATH="${ROOTSYS}/lib:${LD_LIBRARY_PATH}"
ENV PYTHONPATH="${ROOTSYS}/lib:${PYTHONPATH}"

# Setup pachyderm
ENV PACHYDERM_ROOT /opt/pachyderm
# We intentionally make the directory before setting it as the workdir so the directory is made with user permissions
# (workdir always creates the directory with root permissions)
RUN mkdir -p ${PACHYDERM_ROOT}
WORKDIR ${PACHYDERM_ROOT}

# Copy pachyderm into the image.
COPY --chown=overwatch:overwatch . ${PACHYDERM_ROOT}

# Install pachyderm.
RUN pip install --user --upgrade --no-cache-dir -e .[tests,dev,docs]
