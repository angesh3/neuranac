# TLS Certificates for RadSec and Services

**Do not commit private keys (`.key`, `.pem`) to the repository.**

## Generating certificates

For local development and testing, generate self-signed certs:

```bash
# CA
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 -out ca.crt \
  -subj "/CN=NeuraNAC-CA"

# Server cert (RadSec, TLS)
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr -subj "/CN=localhost"
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 365 -sha256

# RadSec client cert (optional)
openssl genrsa -out radsec.key 2048
openssl req -new -key radsec.key -out radsec.csr -subj "/CN=neuranac-radsec"
openssl x509 -req -in radsec.csr -CA ca.crt -CAkey ca.key \
  -out radsec.crt -days 365 -sha256
```

For production, use your organization's PKI or a service like cert-manager.
