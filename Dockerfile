FROM node:10-jessie

RUN apt-get update -y && \
    apt-get install -y gconf-service libasound2 libatk1.0-0 libc6 libcairo2 libcups2 libdbus-1-3 libexpat1 libfontconfig1 libgcc1 libgconf-2-4 libgdk-pixbuf2.0-0 libglib2.0-0 libgtk-3-0 libnspr4 libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 libxtst6 ca-certificates fonts-liberation libappindicator1 libnss3 lsb-release xdg-utils wget libgbm1 && \
    apt-get clean && rm -rf /tmp/* /var/lib/apt/lists/* /var/tmp/*
RUN mkdir -p /home/node/flaresolverr && chown -R node:node /home/node/flaresolverr
WORKDIR /home/node/flaresolverr

COPY package*.json ./
USER node
RUN npm install
COPY --chown=node:node . .

ENV LOG_LEVEL=info
ENV LOG_HTML=false
ENV PORT=8191
ENV HOST=0.0.0.0

EXPOSE 8191
CMD [ "node", "index.js" ]
