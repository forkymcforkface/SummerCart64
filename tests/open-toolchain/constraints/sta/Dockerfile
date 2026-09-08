# Research-only OpenSTA fixture environment; no FPGA timings or hardware tools.
FROM sc64-open:diagnostic
RUN apt-get update && apt-get install -y --no-install-recommends \
    bison flex libfl-dev swig tcl-dev zlib1g-dev libgtest-dev autoconf automake libtool
RUN git clone https://github.com/cuddorg/cudd.git /src/cudd && \
    git -C /src/cudd checkout f54f533303640afd5dbe47a05ebeabb3066f2a25 && \
    cd /src/cudd && autoreconf -fi && ./configure --prefix=/opt/cudd && \
    make -j2 && make install
RUN git clone https://github.com/The-OpenROAD-Project/OpenSTA.git /src/OpenSTA && \
    git -C /src/OpenSTA checkout a9a3f30ca97dc13f9ef911cae1a82c42c67379e1 && \
    cmake -S /src/OpenSTA -B /src/OpenSTA/build \
        -DCMAKE_BUILD_TYPE=Release -DCUDD_DIR=/opt/cudd && \
    cmake --build /src/OpenSTA/build --target sta -j2
