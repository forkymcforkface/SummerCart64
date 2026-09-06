# Research-only MachXO2 toolchain; no Diamond installation or license file.
FROM ubuntu:24.04@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517
ADD --checksum=sha256:a638bbe7f0559fc5b744a92815666179cb71f45e5c4004d4bc9f7e8310d690d9 https://github.com/YosysHQ/oss-cad-suite-build/releases/download/2026-09-05/oss-cad-suite-linux-x64-20260905.tgz /tmp/suite.tgz
RUN tar xzf /tmp/suite.tgz -C /opt && rm /tmp/suite.tgz
ENV PATH="/opt/oss-cad-suite/bin:${PATH}"
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git ca-certificates python3-dev python3-setuptools \
    libboost-all-dev libeigen3-dev zlib1g-dev && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/YosysHQ/prjtrellis.git /src/prjtrellis && \
    cd /src/prjtrellis && git checkout 3afe7b52b30f4b4417ee98f03016767a502006e3 && \
    git submodule update --init --recursive && \
    cmake -S libtrellis -B libtrellis/build -DCMAKE_INSTALL_PREFIX=/usr/local && \
    cmake --build libtrellis/build -j4 && cmake --install libtrellis/build
RUN git clone https://github.com/YosysHQ/nextpnr.git /src/nextpnr && \
    cd /src/nextpnr && git checkout 8dbcee5c3c4415770b6fd06d5ccb2db89545b8ec && \
    git submodule update --init --recursive && \
    cmake -S . -B build -DARCH=machxo2 -DMACHXO2_DEVICES=7000 \
        -DBUILD_GUI=OFF -DCMAKE_INSTALL_PREFIX=/usr/local && \
    cmake --build build -j4 && cmake --install build
ENV PATH="/usr/local/bin:/opt/oss-cad-suite/bin:${PATH}"
RUN nextpnr-machxo2 --list-devices 2>&1 | grep -F LCMXO2-7000HC-6TG144C
