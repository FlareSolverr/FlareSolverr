FROM python:3.10-slim-bullseye as builder

# Build dummy packages to skip installing them and their dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends equivs \
    && equivs-control libgl1-mesa-dri \
    && printf 'Section: misc\nPriority: optional\nStandards-Version: 3.9.2\nPackage: libgl1-mesa-dri\nVersion: 99.0.0\nDescription: Dummy package for libgl1-mesa-dri\n' >> libgl1-mesa-dri \
    && equivs-build libgl1-mesa-dri \
    && mv libgl1-mesa-dri_*.deb /libgl1-mesa-dri.deb \
    && equivs-control adwaita-icon-theme \
    && printf 'Section: misc\nPriority: optional\nStandards-Version: 3.9.2\nPackage: adwaita-icon-theme\nVersion: 99.0.0\nDescription: Dummy package for adwaita-icon-theme\n' >> adwaita-icon-theme \
    && equivs-build adwaita-icon-theme \
    && mv adwaita-icon-theme_*.deb /adwaita-icon-theme.deb

FROM python:3.10-slim-bullseye

# Copy dummy packages
COPY --from=builder /*.deb /

# Install dependencies and create flaresolverr user
# We have to install and old version of Chromium because its not working in Raspberry Pi / ARM
# You can test Chromium running this command inside the container:
#    xvfb-run -s "-screen 0 1600x1200x24" chromium --no-sandbox
# The error traces is like this: "*** stack smashing detected ***: terminated"
# To check the package versions available you can use this command:
#    apt-cache madison chromium
WORKDIR /app
RUN echo "\ndeb http://snapshot.debian.org/archive/debian/20210519T212015Z/ bullseye main" >> /etc/apt/sources.list \
    && echo 'Acquire::Check-Valid-Until "false";' | tee /etc/apt/apt.conf.d/00snapshot \
    # Install dummy packages
    && dpkg -i /libgl1-mesa-dri.deb \
    && dpkg -i /adwaita-icon-theme.deb \
    # Install dependencies
    && apt-get update \
    && apt-get install -y --no-install-recommends chromium=89.0.4389.114-1 chromium-common=89.0.4389.114-1 \
    chromium-driver=89.0.4389.114-1 xvfb \
    # Remove temporary files and hardware decoding libraries
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /usr/lib/x86_64-linux-gnu/libmfxhw* \
    && rm -f /usr/lib/x86_64-linux-gnu/mfx/* \
    # Create flaresolverr user
    && useradd --home-dir /app --shell /bin/sh flaresolverr \
    && mv /usr/bin/chromedriver chromedriver \
    && chown -R flaresolverr:flaresolverr .

# Install Python dependencies
RUN pip install pipenv
COPY Pipfile .
COPY Pipfile.lock .
RUN pipenv install --system --deploy --ignore-pipfile \
    # Remove temporary files
    && rm -rf /root/.cache \
    && find / -name '*.pyc' -delete

USER flaresolverr

COPY src .
COPY package.json ../

EXPOSE 8191

CMD ["/usr/local/bin/python", "-u", "/app/flaresolverr.py"]

# Local build
# docker build -t ngosang/flaresolverr:3.0.0.beta2 .
# docker run -p 8191:8191 ngosang/flaresolverr:3.0.0.beta2

# Multi-arch build
# docker buildx create --use
# docker buildx build -t ngosang/flaresolverr:3.0.0.beta2 --platform linux/386,linux/amd64,linux/arm/v7,linux/arm64/v8 .
#   add --push to publish in DockerHub
