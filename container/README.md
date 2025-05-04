# Local deployment
Deploy a local stack locally using `podman`.

## Preparation
* Get the model:
```shell
wget https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q5_K_M.gguf
```
* Create a local network:
```shell
podman network create llama-net
```

---

## Deploy the Llama server
```shell
podman run -d --name llama-server \
  --network llama-net \
  -p 8080:8080 \
  -v "$(pwd)/models:/models:z" \
  ghcr.io/ggml-org/llama.cpp:server \
  -m /models/mistral-7b-instruct-v0.2.Q5_K_M.gguf -c 512 --host 0.0.0.0 --port 8080
```
You can test the Llama server with `curl`:
```shell
curl --request POST \
     --url http://0.0.0.0:8080/completion \
     --header "Content-Type: application/json" \
     --data '{"prompt": "what is the result of 2+2?","n_predict": 128}'
```

---

## Deploy the API container:
* Build the image:
```shell
podman build -t api -f container/Dockerfile .
```
* Define the required environment variables:
```shell
export SLACK_TOKEN=your-slack-token
export USER_TOKEN=your-user-token
```
* Deploy the container
```shell
podman run -d --name api \
  --network llama-net \
  -p 8000:8000 \
  -e USER_TOKEN=${USER_TOKEN} \
  -e SLACK_TOKEN=${SLACK_TOKEN} \
  -e LLAMA_SERVER_HOST="llama-server" \
  -e LLAMA_SERVER_PORT="8080" \
  api
```

## Test the local deployment
```shell
curl --url http://127.0.0.1:8000/summarize-url?url=https://redhat-internal.slack.com/archives/GDBRP5YJH/p1746057618660169
```

---

# OCP deployment
## Store the Llama model in a PVC:
1. Create the PVC:
   ```shell
   oc apply -f resources/llama-model-pvc.yaml
   ```
2. Create an ephemeral pod:
    ```shell
    oc apply -f model-uploader.yaml
    ```
3. Attach a shell to the ephemeral pod:
   ```shell
    oc exec -ti model-uploader bash
    ```
4. Once inside the pod, install `wget` and download the model:
   ```shell
   dnf install -y wget
   wget https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q5_K_M.gguf
   ```
5. Verify that the model has been uploaded:
   ```shell
    oc exec -it model-uploader -- ls -lh /models
    ```
6. Delete the emphemeral pod:
    ```shell
    oc delete pod/model-uploader
    ```
   
---

## Deploy the Llama server
* Create the deployment:
```shell
oc apply -f resources/llama-deployment.yaml
```
* Expose the deployment
```shell
oc apply -f resources/llama-service.yaml
```
* Test it from an ephemeral pod:
```shell
oc run --rm -ti test --image=registry.access.redhat.com/ubi8/ubi -- \
   curl -v http://llama-service/completion \
   -H "Content-Type: application/json" \
   -d '{"prompt": "what is the result of 2+2?", "n_predict": 8}'
```

---

## Deploy the API application
* Create the Imagestream:
   ```shell
   oc apply -f container/resources/slack-summarizer-is.yaml
   ```
* Create the BuildConfig:
   ```shell
   oc apply -f container/resources/slack-summarizer-is.yaml
   ```
* Create the ConfigMap:
   ```shell
   oc apply -f container/resources/llama-server-config.yaml
   ```
* Create a secret to named `slack-credentials` to hold the environment variables needed by Slack
   ```shell
   $ oc get secret slack-credentials -o yaml
   apiVersion: v1
   data:
     slack_token: your-slack-token
     user_token: your-user-token
   kind: Secret
   metadata:
     name: slack-credentials
   type: Opaque
   ```
* Create the deployment:
   ```shell
   oc apply -f container/resources/slack-summarizer-deployment.yaml
   ```
* Expose the deployment:
   ```shell
   oc apply -f container/resources/slack-summarizer-svc.yaml
   ```
* Create the route, with a long timeout to account for slow model responses:
   ```shell
   oc apply -f container/resources/slack-summarizer-route.yaml
   ```

---

## Test the OCP deployment
```shell
curl --url https://slack-summarizer-{namespace}.apps.artc2023.pc3z.p1.openshiftapps.com/summarize-url?url=https://redhat-internal.slack.com/archives/GDBRP5YJH/p1746057618660169

curl --url https://slack-summarizer-{namespace}.apps.artc2023.pc3z.p1.openshiftapps.com/summarize-art-attention
```