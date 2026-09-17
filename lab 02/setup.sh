#!/usr/bin/env bash
# Provisions the resources for Lab 2:
#  - resource group
#  - ADLS Gen2 storage account with the source file (files/data/Product.csv)
#  - Azure SQL Database (free offer) with the dbo.DimProduct table
#  - Azure Data Factory
# Run it from Azure Cloud Shell (Bash): ./setup.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting setup at $(date)"
echo "Using subscription: $(az account show --query name -o tsv)"
echo

# Region: must be one of the allowed regions of your student subscription (see Lab 1)
LOCATION="${LOCATION:-}"
if [ -z "$LOCATION" ]; then
    read -rp "Enter one of your allowed regions (e.g. polandcentral, germanywestcentral, italynorth): " LOCATION
fi

# Password for the SQL admin user
SQLUSER="sqladmin"
while true; do
    echo
    echo "Enter a password for the '$SQLUSER' SQL login."
    echo "It must be at least 8 characters long and contain upper case letters, lower case letters and digits."
    read -rsp "Password: " SQLPASSWORD
    echo
    if [ ${#SQLPASSWORD} -ge 8 ] && [[ "$SQLPASSWORD" =~ [A-Z] ]] && [[ "$SQLPASSWORD" =~ [a-z] ]] && [[ "$SQLPASSWORD" =~ [0-9] ]]; then
        echo "Password accepted. Make sure you remember it!"
        break
    fi
    echo "The password does not meet the complexity requirements."
done

# Random suffix for globally unique resource names
SUFFIX="$(head -c 32 /dev/urandom | md5sum | cut -c1-7)"
RG="dp-lab2-$SUFFIX"
STORAGE="datalake$SUFFIX"
SQLSERVER="sql-lab2-$SUFFIX"
SQLDB="productdw"
ADF="adf-lab2-$SUFFIX"

echo
echo "Registering resource providers (this may take a few minutes)..."
for provider in Microsoft.Storage Microsoft.Sql Microsoft.DataFactory; do
    az provider register --namespace "$provider" --wait
    echo "  $provider: registered"
done

echo "Creating resource group $RG in $LOCATION..."
az group create --name "$RG" --location "$LOCATION" -o none

echo "Creating storage account $STORAGE (Data Lake Storage Gen2)..."
az storage account create --name "$STORAGE" --resource-group "$RG" --location "$LOCATION" \
    --sku Standard_LRS --kind StorageV2 --hns true \
    --min-tls-version TLS1_2 --allow-blob-public-access false -o none
STORAGE_KEY="$(az storage account keys list --account-name "$STORAGE" --resource-group "$RG" --query "[0].value" -o tsv)"

echo "Uploading source data..."
az storage fs create --name files --account-name "$STORAGE" --account-key "$STORAGE_KEY" -o none
az storage fs file upload --file-system files --source "$SCRIPT_DIR/data/Product.csv" --path data/Product.csv \
    --account-name "$STORAGE" --account-key "$STORAGE_KEY" --overwrite -o none

echo "Creating SQL server $SQLSERVER..."
az sql server create --name "$SQLSERVER" --resource-group "$RG" --location "$LOCATION" \
    --admin-user "$SQLUSER" --admin-password "$SQLPASSWORD" -o none

# 0.0.0.0 is a special rule: allow access from Azure services (needed by Data Factory)
az sql server firewall-rule create --resource-group "$RG" --server "$SQLSERVER" --name AllowAzureServices \
    --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 -o none

# allow access from this Cloud Shell session to run the setup SQL script
MYIP="$(curl -s https://api.ipify.org || true)"
if [ -n "$MYIP" ]; then
    az sql server firewall-rule create --resource-group "$RG" --server "$SQLSERVER" --name CloudShell \
        --start-ip-address "$MYIP" --end-ip-address "$MYIP" -o none
fi

echo "Creating SQL database $SQLDB (free offer, serverless)..."
az sql db create --name "$SQLDB" --resource-group "$RG" --server "$SQLSERVER" \
    --edition GeneralPurpose --family Gen5 --capacity 2 --compute-model Serverless \
    --use-free-limit true --free-limit-exhaustion-behavior AutoPause \
    --backup-storage-redundancy Local -o none

echo "Creating the dbo.DimProduct table..."
SQL_DONE=0
if command -v sqlcmd > /dev/null; then
    for attempt in 1 2 3; do
        if SQLCMDPASSWORD="$SQLPASSWORD" sqlcmd -S "tcp:$SQLSERVER.database.windows.net,1433" -d "$SQLDB" \
            -U "$SQLUSER" -i "$SCRIPT_DIR/setup.sql" -b; then
            SQL_DONE=1
            break
        fi
        echo "  Database is not reachable yet, retrying in 30 seconds..."
        sleep 30
    done
fi

echo "Creating data factory $ADF..."
az config set extension.use_dynamic_install=yes_without_prompt -o none 2> /dev/null || true
ADF_DONE=0
if az datafactory create --name "$ADF" --resource-group "$RG" --location "$LOCATION" -o none; then
    ADF_DONE=1
fi

cat > "$HOME/lab2.env" << EOF
export RG="$RG"
export STORAGE="$STORAGE"
export SQLSERVER="$SQLSERVER"
export SQLDB="$SQLDB"
export SQLUSER="$SQLUSER"
export ADF="$ADF"
EOF

echo
echo "============================================================"
echo "Setup finished at $(date)"
echo
echo "  Resource group:   $RG"
echo "  Storage account:  $STORAGE"
echo "  SQL server:       $SQLSERVER.database.windows.net"
echo "  SQL database:     $SQLDB"
echo "  SQL user:         $SQLUSER"
echo "  Data factory:     $ADF"
echo
echo "These names are also saved to ~/lab2.env (use: source ~/lab2.env)"
echo "============================================================"

if [ "$SQL_DONE" -ne 1 ]; then
    echo
    echo "WARNING: the dbo.DimProduct table could not be created automatically."
    echo "Open the $SQLDB database in the Azure portal, go to 'Query editor', log in with"
    echo "the $SQLUSER user and run the content of setup.sql manually."
fi

if [ "$ADF_DONE" -ne 1 ]; then
    echo
    echo "WARNING: the data factory could not be created in $LOCATION."
    echo "Create it manually in the Azure portal (Data factories > Create) in the $RG resource group,"
    echo "choosing another region from your allowed region list."
fi
