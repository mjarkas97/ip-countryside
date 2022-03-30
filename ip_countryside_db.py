import json

from config import *;


# @TODO
# Implement an exctract to YAML method      -> Aufwand 5


def read_db(file=IP2COUNTRY_DB):

    records = []
    try:

        # save all records into a list
        with open(file, "r", encoding='utf-8', errors='ignore') as f:
            
            for line in f:
                
                record = read_db_record(line)
                
                if(record):
                    
                    records.append(record)

    except IOError as e:
        
        print(e)

    return records


def read_db_record(line):
    
    # record index:    0       1   2    3           4            5          
    # record format: ip_from|ip_to|cc|registry|description|last-modified|

    if line.startswith("\n"):
        return []

    line = line.split("|")

    if(len(line) >= 3):

        ip_from         = int(line[0]) 
        ip_to           = int(line[1]) 
        country         = line[2].upper()
        registry        = line[3].rstrip('\n').upper()
        descr           = ""
        last_modified   = ""

        if len(line) >= 5:
            descr = line[4].rstrip("\n")

        if len(line) >= 6:
            last_modified = line[5].rstrip("\n")

        return [ip_from, ip_to, country, registry, descr, last_modified]

    return []


def extract_as_json(file=IP2COUNTRY_DB):
    
    data = { }
    
    records = read_db(file)
    
    try :

        with open(IP2COUNTRY_DB_JSON, 'w',  encoding='utf-8', errors='ignore') as f:
            
            f.write("[\n")
          
            for recod in records:
                
                data = {
                    'ipFrom':        recod[0],
                    'ipTo':          recod[1],
                    'CountryCode':   recod[2],
                    'Registry':      recod[3],
                    'Description':   recod[4],
                    'LastModified':  recod[5],
                }

                f.write(json.dumps(data, indent=4))
            
                f.write(",\n")
            
            f.write("]")

    except IOError as e:

        print(e)

    return 0


def extract_as_yaml(file=IP2COUNTRY_DB):
    pass


# later -> sql lite... 