# Lab 1 - Introduction to Azure Cloud

## Task 1: Register a student account to Azure

Use your `@elte.hu` email address to register a student account in Azure:
[https://azure.microsoft.com/en-us/free/students](https://azure.microsoft.com/en-us/free/students)

You can use many services for free, and you'll also get 100$ free credit to use.

## Task 2: Use the Azure portal to start a free tier Linux VM

Azure for Students accounts restrict deployments to typically five specific regions, which vary by user due to policy and capacity limits. [learn.microsoft](https://learn.microsoft.com/en-us/answers/questions/5632051/about-storage-account-regions-for-students-account)

To check regions in portal, log into the Azure Portal and go to Policy > Authoring > Assignments (direct link: https://portal.azure.com/#view/Microsoft_Azure_Policy/PolicyMenuBlade/~/Assignments). Look for the "Allowed resource deployment regions" assignment, open it, and check the "Allowed locations" parameter values for your list of permitted regions. [learn.microsoft](https://learn.microsoft.com/en-us/answers/questions/5742238/how-do-i-find-out-which-regions-i-can-use-on-my-az)

There is no Azure region in Hungary, so pick one of your allowed regions that is close to us, e.g. `Poland Central`, `Germany West Central`, `Austria East` or `Italy North`.

Note: a region being allowed does not guarantee that every VM size is available there. If VM creation fails with a SKU or capacity error, try another size or another allowed region.

Type `Free services` into the search field to navigate to the Free Tier blade.
Use the `Linux Virtual Machine` option to start a virtual machine.

You'll need to create a new `Resource Group` for the VM.
Select a region that is supported by your Student Account, and it is close to us.

For the VM size, choose `Standard_B2ats_v2` (x86, included in the free tier).
The older `Standard_B1s` size is being retired and is usually not available for new subscriptions.
Avoid `B2pts v2`, it is an ARM-based machine and needs an ARM image.

Also, add the `HTTP` option at the bottom at `Select inbound ports` in order to allow traffic on port `80/TCP`.
Finally, click the `Review + create` button.

An `ssh key` was also generated for the VM which is downloaded to your machine.
You can use this key to log into the machine:
```
ssh -i <key name>.pem azureuser@<VM public IP>
```

If you're done with the experiment, delete the VM using the portal.
Also check the `Resource Group` and delete it as well (this removes the disk and public IP too, which otherwise keep consuming your credit).

**Important:** Azure for Students subscriptions have a quota of 4 vCPUs. The `Standard_B2ats_v2` VM uses 2 vCPUs, so delete this VM before continuing with Task 3!

## Task 3: Use the Azure CLI for the same Task

You can also use the Azure CLI called `az` to do the same task.
The most convenient way would be using Azure CloudShell (top right corner).
But if you'd like to run it locally on your computer, you can install it like this (you can skip this with CloudShell):

```
# install az cli tool: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# login to your Azure account
az login

# If no web browser is available or if the web browser fails to open, use device code flow with `az login --use-device-code`
```

Execute some basic commands (continue from here if you're using CloudShell):
```
# list available subscriptions
az account list

# select default subscription
az account set --name "Azure for Students"

# see list of virtual machines
az vm list
```

Use the following commands to start a VM:
```
# set ENV variables for convenience
export VMNAME="my-first-vm"
# use one of YOUR allowed regions (see Task 2), e.g. polandcentral, germanywestcentral, austriaeast, italynorth
export LOCATION="polandcentral"

# check which B-series sizes are available for your subscription in that region
# (if the Restrictions column says NotAvailableForSubscription, choose another size or region)
az vm list-skus --location $LOCATION --size Standard_B --all -o table

# create your first VM --> should result in error
az vm create --name $VMNAME --resource-group $VMNAME-rg --size Standard_B2ats_v2 --image Ubuntu2404

# create the resource group first in your region
az group create --name $VMNAME-rg --location $LOCATION

# now create the VM again (an SSH keypair is generated in ~/.ssh if you don't have one yet)
az vm create -n $VMNAME -g $VMNAME-rg --size Standard_B2ats_v2 --image Ubuntu2404 --admin-username azureuser --generate-ssh-keys

# open port 80 for HTTP traffic
az vm open-port --port 80 --resource-group $VMNAME-rg --name $VMNAME

# get public IP of the VM and SSH to it
ssh azureuser@$(az vm list-ip-addresses --name $VMNAME --resource-group $VMNAME-rg --query "[].virtualMachine.network.publicIpAddresses[0].ipAddress" -o tsv)
```

## Task 4: Run a hello world example

In this example we'll create a simple web service in Go that will be reachable via the public internet.

First, we'll install the Go SDK to be able to build Go projects:
```
sudo apt update
sudo apt install -y golang
```

Create the simple Go app in a dedicated project directory:
```
mkdir hello-world
cd hello-world

# we just download the example from GitHub
wget https://raw.githubusercontent.com/elte-cloud-native/go-web-example/master/webserver.go
# you can check the content
cat webserver.go

# some Go command required to set up the project
go mod init github.com/myname/myproject
go mod tidy

# build the project
go build -o hello-world .

# run the application (you'll need sudo for opening port 80)
sudo ./hello-world
```

Now try to access the application either by a browser or with following command:
```
curl <vm public ip>
```

## Task 5: Delete the created VMs

!!Remember!!

Always clean up unused resources in cloud in order to not waste money!

Deleting the resource group removes everything inside it: the VM, its disk, network interface and public IP.
(Deleting only the VM with `az vm delete` may leave the disk and public IP behind, which still cost money.)

```
# delete the resource group with all resources in it
az group delete --name $VMNAME-rg --yes --no-wait

# check that nothing is left
az group list -o table
```
