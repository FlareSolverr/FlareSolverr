FROM --platform=${TARGETPLATFORM:-linux/amd64} node:15.2.1-alpine3.11

# Print build information
ARG TARGETPLATFORM
ARG BUILDPLATFORM
RUN printf "I am running on ${BUILDPLATFORM:-linux/amd64}, building for ${TARGETPLATFORM:-linux/amd64}\n$(uname -a)\n"

# Install Chromium, dumb-init and remove all locales but en-US
RUN apk add --no-cache chromium dumb-init && \
    find /usr/lib/chromium/locales -type f ! -name 'en-US.*' -delete

# Copy FlareSolverr code
USER node
RUN mkdir -p /home/node/flaresolverr
WORKDIR /home/node/flaresolverr
COPY --chown=node:node package.json package-lock.json tsconfig.json ./
COPY --chown=node:node src ./src/

# Install package. Skip installing Chrome, we will use the installed package.
ENV PUPPETEER_PRODUCT=chrome \
    PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser
RUN npm install && \
    npm run build && \
    npm prune --production && \
    rm -rf /home/node/.npm

EXPOSE 8191
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["npm", "start"]
