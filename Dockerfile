FROM python:3.10.5-slim-bullseye

WORKDIR /app

# Install dependencies and create user
# We have to install and old version of Chromium because its not working in Raspberry Pi / ARM
# You can test Chromium running this command inside the container:
#    xvfb-run -s "-screen 0 1600x1200x24" chromium --no-sandbox
# The error traces is like this: "*** stack smashing detected ***: terminated"
# To check the package versions available you can use this command:
#    apt-cache madison chromium
RUN echo "\ndeb http://snapshot.debian.org/archive/debian/20210519T212015Z/ bullseye main" >> /etc/apt/sources.list \
    && echo 'Acquire::Check-Valid-Until "false";' | tee /etc/apt/apt.conf.d/00snapshot \
    && apt-get update \
    && apt-get install -y --no-install-recommends chromium=89.0.4389.114-1 chromium-common=89.0.4389.114-1 \
        chromium-driver=89.0.4389.114-1 xvfb xauth \
    # Clean
    && rm -rf /var/lib/apt/lists/* \
    # Create user
    && useradd --home-dir /app --shell /bin/sh flaresolverr \
    && mv /usr/bin/chromedriver chromedriver \
    && chown -R flaresolverr:flaresolverr .

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt \
    # remove temporary files
    && rm -rf /root/.cache \
    && find / -name '*.pyc' -delete

USER flaresolverr

COPY src .
COPY package.json ../

EXPOSE 8191

CMD ["/usr/local/bin/python", "-u", "/app/flaresolverr.py"]

# docker build -t flaresolverr:3.0.0.beta1 .
# docker run -p 8191:8191 flaresolverr:3.0.0.beta1
