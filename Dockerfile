FROM python:3.11-slim

WORKDIR /ansible

# Install Ansible and the paramiko SSH backend
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Ansible Galaxy collections (cisco.ios, ansible.netcommon)
COPY requirements.yml ./
RUN ansible-galaxy collection install -r requirements.yml

# Copy the rest of the project
COPY . .

# Default: run the callback plugin demo playbook on localhost
ENTRYPOINT ["ansible-playbook"]
CMD ["playbooks/demo_callback.yml"]
