FROM ubuntu:16.04

ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONUNBUFFERED 1
ENV PYTHONIOENCODING utf8

RUN set -ex \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        apt-transport-https \
        curl \
        git \
        build-essential \
        python-software-properties \
        python-pip \
        python-dev \
        libmysqlclient-dev \
        software-properties-common \
        libldap2-dev \
        libsasl2-dev \
    && rm -rf /var/lib/apt/lists/*

ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8

RUN curl "https://bootstrap.pypa.io/get-pip.py" -o "get-pip.py"
RUN python get-pip.py
RUN pip install --upgrade pip
RUN pip install wheel

RUN mkdir -p /usr/src/old
COPY . /usr/src/old
WORKDIR /usr/src/old
RUN python setup.py install
CMD tail -f /dev/null



