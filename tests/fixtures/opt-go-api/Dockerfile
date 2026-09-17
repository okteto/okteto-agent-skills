# Intentionally un-optimized: unpinned base, COPY . . before deps, no cache mount.
FROM golang:latest
WORKDIR /app
COPY . .
RUN go build -o /usr/src/api
CMD ["/usr/src/api"]
