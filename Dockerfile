FROM condaforge/miniforge3:latest

# Install MRtrix3 via conda-forge
RUN mamba install -y -c conda-forge -c MRtrix3 mrtrix3 libstdcxx-ng python=3.11 && mamba clean -afy

# Copy and install qsiparc
WORKDIR /opt/qsiparc
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir .

# Verify both tools are available
RUN tck2connectome --version && qsiparc --help

ENTRYPOINT ["qsiparc"]
