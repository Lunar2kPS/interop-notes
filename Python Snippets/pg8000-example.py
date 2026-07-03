import os
import logging
import ssl
import pg8000.dbapi
from typing import Dict, List, Any

from azure.identity import ClientSecretCredential

logger = logging.getLogger(__name__)

# Entra ID token scope for PostgreSQL Azure Database:
AAD_PG_SCOPE = "<REDACTED>"

class DatabaseManager:
    def __init__(self, config):
        self.config = config
        self.connection = None

    def _get_aad_token(self) -> str:
        # 1. Suppress Azure Identity chatter, including token-request HTTP info:
        # 2. Suppress azure-core HTTP request/response logging policy output:
        logging.getLogger("azure.identity").setLevel(logging.WARNING)
        logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)

        missing = [v for v in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET") if not os.getenv(v)]
        if missing:
            raise ValueError(f"DB_AUTH=aad requires environment variables: {', '.join(missing)}")

        credential = ClientSecretCredential(
            tenant_id=os.environ["AZURE_TENANT_ID"],
            client_id=os.environ["AZURE_CLIENT_ID"],
            client_secret=os.environ["AZURE_CLIENT_SECRET"],
        )
        # Token is short-lived (~60-90 min); fetched fresh on each connect().
        return credential.get_token(AAD_PG_SCOPE).token
    
    def connect(self):
        """Connect to PostgreSQL database (Entra ID token or static password)."""
        try:
            if getattr(self.config, 'dbAuth', 'password') == 'aad':
                password = self._get_aad_token()
                logger.info("Authenticating to PostgreSQL with a Microsoft Entra ID access token.")
            else:
                password = self.config.dbPassword

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            self.connection = pg8000.dbapi.connect(
                host=self.config.dbServer,
                database=self.config.dbName,
                user=self.config.dbUsername,
                password=password,
                port=5432,
                ssl_context=ssl_context,
            )
            logger.info(f"Connected to database: {self.config.dbServer}/{self.config.dbName}")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def close(self):
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed.")

    def exampleQueryFunction(self, intParam: int, stringParam: str) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM <DATABASE>.<TABLE>
                WHERE <REDACTED> = %s
                AND <REDACTED> = %s
                AND <REDACTED> = '<REDACTED>'
                ORDER BY <REDACTED>, <REDACTED>, <REDACTED>, <REDACTED>;
        """

        try:
            cursor = self.connection.cursor()
            try:
                cursor.execute(query, (intParam, stringParam))
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
            finally:
                cursor.close()
        except Exception as e:
            logger.error(f"An error occurred while trying to fetch data from the database: {e}")
