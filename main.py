import os
import subprocess
import time
import requests

def start_service(service_name):
    print(f"Starting {service_name}...")
    result = subprocess.run(["docker", "compose", "up", "-d", service_name], capture_output=True)
    if result.returncode != 0:
        print(f"Failed to start {service_name}: {result.stderr.decode()}")
        exit(1)

def check_service_running(container_name):
    print(f"Checking {container_name} service status...")
    result = subprocess.run(["docker", "ps"], capture_output=True, text=True)
    if container_name not in result.stdout:
        print(f"{container_name} service failed to start. Exiting.")
        exit(1)

def wait_for_elasticsearch():
    print("Waiting for Elasticsearch to be ready...")
    while True:
        try:
            response = requests.get("http://localhost:9200", auth=("elastic", "admin1234"))
            if response.status_code == 200:
                print("Elasticsearch is ready.")
                break
        except requests.RequestException:
            pass
        print("Elasticsearch is not ready yet. Retrying in 5 seconds...")
        time.sleep(5)

def set_kibana_password_and_generate_token():
    es_container = "elasticsearch_container"
    print("Setting Kibana system user password and generating token...")
    password_command = (
        "curl -s -X POST -u elastic:admin1234 -H 'Content-Type: application/json' "
        "http://localhost:9200/_security/user/kibana_system/_password -d '{\"password\":\"kibana\"}'"
    )
    token_command = (
        "bin/elasticsearch-service-tokens create elastic/kibana jobber-kibana | "
        "grep 'SERVICE_TOKEN' | awk -F ' = ' '{print $2}'"
    )

    subprocess.run(["docker", "exec", "-i", es_container, "sh", "-c", password_command], check=True)
    time.sleep(5)
    result = subprocess.run(
        ["docker", "exec", "-i", es_container, "sh", "-c", token_command],
        capture_output=True, text=True
    )

    token_value = result.stdout.strip()
    if not token_value:
        print("Failed to retrieve the token from Elasticsearch. Exiting.")
        exit(1)
    print(f"Kibana token retrieved: {token_value}")
    return token_value

def update_docker_compose_yml(token_value):
    print("Updating docker-compose.yaml with the new Kibana token...")
    try:
        updated = False
        new_lines = []
        with open("docker-compose.yaml", "r") as file:
            lines = file.readlines()
        
        for line in lines:
            if "ELASTICSEARCH_SERVICEACCOUNT_TOKEN=" in line:
                new_lines.append(f"      - ELASTICSEARCH_SERVICEACCOUNT_TOKEN={token_value}\n")
                updated = True
            else:
                new_lines.append(line)
        
        if not updated:
            for idx, line in enumerate(new_lines):
                if "environment:" in line and "kibana" in "".join(new_lines[max(0, idx - 5):idx]):
                    new_lines.insert(idx + 1, f"      - ELASTICSEARCH_SERVICEACCOUNT_TOKEN={token_value}\n")
                    updated = True
                    break

        with open("docker-compose.yaml", "w") as file:
            file.writelines(new_lines)
        
        if updated:
            print("docker-compose.yaml updated successfully.")
        else:
            print("Failed to find the Kibana environment block in docker-compose.yaml. No changes made.")
    except Exception as e:
        print(f"Failed to update docker-compose.yaml: {e}")
        exit(1)

def start_kibana():
    print("Starting Kibana...")
    result = subprocess.run(["docker", "compose", "up", "-d", "kibana"], capture_output=True)
    if result.returncode != 0:
        print(f"Failed to start Kibana service: {result.stderr.decode()}")
        exit(1)
    print("Kibana service started successfully.")

def main():
    start_service("elasticsearch")
    check_service_running("elasticsearch_container")
    wait_for_elasticsearch()
    token_value = set_kibana_password_and_generate_token()
    update_docker_compose_yml(token_value)
    start_kibana()
    print("Script completed successfully.")

if __name__ == "__main__":
    main()
