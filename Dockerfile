FROM python:3.11-slim

COPY app /app
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
RUN python -m pip install /app --extra-index-url https://www.piwheels.org/simple

EXPOSE 8020/tcp

LABEL version="0.0.3"

ARG IMAGE_NAME

LABEL permissions='\
{\
  "ExposedPorts": {\
    "8020/tcp": {}\
  },\
  "HostConfig": {\
    "Binds":["/usr/blueos/extensions/$IMAGE_NAME:/app/logs"],\
    "ExtraHosts": ["host.docker.internal:host-gateway"],\
    "NetworkMode": "host",\
    "PortBindings": {\
      "8020/tcp": [\
        {\
          "HostPort": ""\
        }\
      ]\
    }\
  }\
}'

ARG AUTHOR
ARG AUTHOR_EMAIL
LABEL authors='[\
    {\
        "name": "$AUTHOR",\
        "email": "$AUTHOR_EMAIL"\
    }\
]'

ARG MAINTAINER
ARG MAINTAINER_EMAIL
LABEL company='{\
        "about": "",\
        "name": "$MAINTAINER",\
        "email": "$MAINTAINER_EMAIL"\
    }'
LABEL type="example"
ARG REPO
ARG OWNER
LABEL readme='https://raw.githubusercontent.com/$OWNER/$REPO/{tag}/README.md'
LABEL links='{\
        "source": "https://github.com/$OWNER/$REPO"\
    }'
LABEL requirements="core >= 1.1"

ENTRYPOINT ["litestar", "--app-dir", "/app", "--app", "main:app", "run", "--host", "0.0.0.0", "--port", "8020"]
