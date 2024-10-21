import psycopg2
import pandas as pd

class PostGres:
    
    def __init__(self, user, password, dbname, host, port):
        self.user = user
        self.password = password
        self.dbname = dbname
        self.host = host
        self.port = port
        self.pg = psycopg2.connect(f"user={user} password={password} dbname={dbname} host={host} port={port}")
        
    def query(self, query):
        cur = self.pg.cursor()
        df = pd.read_sql_query(query, self.pg)
        cur.close()
        return df