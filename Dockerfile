FROM debian:trixie-slim AS builder

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
    && mv adwaita-icon-theme_*.deb /adwaita-icon-theme.deb \
    && apt-get purge -y --auto-remove equivs \
    && rm -rf /var/lib/apt/lists/*

FROM debian:trixie-slim

# Copy dummy packages
COPY --from=builder /libgl1-mesa-dri.deb /adwaita-icon-theme.deb /

# Install dependencies and create flaresolverr user
WORKDIR /app
COPY requirements.txt .
RUN apt-get update \
    # Install dummy packages
    && dpkg -i /libgl1-mesa-dri.deb \
    && dpkg -i /adwaita-icon-theme.deb \
    && apt-get install -f \
    # Install dependencies
    && apt-get install -y --no-install-recommends chromium xvfb dumb-init \
        procps curl vim xauth python3 python3-pip \
    # Remove temporary files and hardware decoding libraries
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /usr/lib/x86_64-linux-gnu/libmfxhw* \
    && rm -f /usr/lib/x86_64-linux-gnu/mfx/* \
    # Create flaresolverr user
    && useradd --home-dir /app --shell /bin/sh flaresolverr \
    && chown -R flaresolverr:flaresolverr . \
    # Set up Python and install dependencies
    && ln -s /usr/bin/python3 /usr/local/bin/python \
    && pip install --break-system-packages -r requirements.txt \
    # Remove temporary files
    && rm -rf /root/.cache /tmp/*

USER flaresolverr

RUN mkdir -p "/app/.config/chromium/Crash Reports/pending"

COPY src .
COPY package.json ../

EXPOSE 8191
EXPOSE 8192

# dumb-init avoids zombie chromium processes
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

CMD ["/usr/local/bin/python", "-u", "/app/flaresolverr.py"]

# Local build
# docker build -t ngosang/flaresolverr:3.3.21 .
# docker run -p 8191:8191 ngosang/flaresolverr:3.3.21

# Multi-arch build
# docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
# docker buildx create --use
# docker buildx build -t ngosang/flaresolverr:3.3.21 --platform linux/386,linux/amd64,linux/arm/v7,linux/arm64/v8 .
#   add --push to publish in DockerHub

# Test multi-arch build
# docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
# docker buildx create --use
# docker buildx build -t ngosang/flaresolverr:3.3.21 --platform linux/arm/v7 --load .
# docker run -p 8191:8191 --platform linux/arm/v7 ngosang/flaresolverr:3.3.21
