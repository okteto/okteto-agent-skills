# Intentionally un-optimized: an unpinned base and COPY . . that the
# okteto-manifest-optimizer skill should improve (pin, order layers, cache mounts).
FROM node:latest
WORKDIR /usr/src/app
COPY . .
RUN npm install
RUN chown -R node:node /usr/src/app
CMD ["npm", "run", "dev"]
