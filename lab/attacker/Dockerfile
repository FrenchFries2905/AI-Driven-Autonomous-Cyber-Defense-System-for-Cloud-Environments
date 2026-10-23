# Attacker image: nmap (port scans) and hping3 (floods). Lab use only.
FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends nmap hping3 curl iputils-ping procps \
    && rm -rf /var/lib/apt/lists/*

COPY attacks /attacks
# strip Windows line endings, make the scripts runnable
RUN sed -i 's/\r$//' /attacks/*.sh && chmod +x /attacks/*.sh

WORKDIR /attacks
CMD ["sleep", "infinity"]
