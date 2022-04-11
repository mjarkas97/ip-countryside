import re
import os
import shutil
import fileinput
import ipaddress
import time
from datetime import datetime
#import locationtagger
import multiprocessing as mp

from config import *;
from ip_countryside_db import *;
from ip_countryside_utilities import *;

# Release 0.9.0 coming soon ... 

# @TODO handle_ranges_overlapp() have now a structure to modify the data                    # Aufwand 5
# base records. (The PDF can be helpful)           
# Info: we need to know which entries should be removed. 

# @TODO Bugfix in parse_inet_group() -> see todo there ...                                  # Auufwand 5 

# @TODO comment and write description for each method & clean code                          # Aufwand 5 

# @TODO later add parameters for the command line interpreter (cli)                         # Aufwand 5

# @TODO Flussdiagramm vom Parser erstellen                                                  # Aufwand 5

# @TODO MAX MindDB API importieren zum testen und anschauen benutzen                        # Aufwand 8
# wie sie die Objekte einer Datenbank aufbauen ....

# @TODO Speed up parsing process of inetnum files                                           # Aufwand 13/20
# Parsing should be done by multiple threads

# @TODO add city information (when available) to the method parse_inet parse_inet_group     # Aufwand 21


# ==============================================================================
# Delegation parsing methods 


def merge_del_files():

    try: 
        
        # merges the delegated files into a one file 
        with open(MERGED_DEL_FILE, "wb") as f:
            
            for del_file in [ 
                    os.path.join(DEL_FILES_DIR, AFRINIC['del_fname']), 
                    os.path.join(DEL_FILES_DIR, LACNIC['del_fname']),
                    os.path.join(DEL_FILES_DIR, ARIN['del_fname']),
                    os.path.join(DEL_FILES_DIR, APNIC['del_fname']), 
                    os.path.join(DEL_FILES_DIR, RIPE['del_fname'])
                    ]:

                with open(del_file, "rb") as source:

                    shutil.copyfileobj(source, f)

                    f.write(os.linesep.encode())
    
    except IOError as e:
        
        print(e)


def parse_del_files():

    try:

        with open(STRIPPED_DEL_FILE, "w") as f:

            for line in fileinput.input(MERGED_DEL_FILE):
                
                # get rid of all lines without "ip entry" before parsing
                if re.search(IPV4_PATTERN, line) or re.search(IPV6_PATTERN, line):

                    # actual parsing of a line is done in parse_del_line
                    record = parse_del_line(line)
                    
                    if record:

                        line = "|".join(map(str, record))
                        line = line + '\n'
                        f.write(line)

    except IOError as e:
        
        print(e)


def parse_del_line(line):          
    
    # record index:     0      1   2    3     4     5    6
    # record format: registry|cc|type|start|value|date|status[|extensions...]

    record = []
    record = line.split("|")

    # extract infromation from line
    registry    = record[0].upper()
    country     = record[1].upper()
    type        = record[2]
    network_ip  = record[3]
    mask        = record[4]
    date        = record[5]
    status      = record[6]
    record_type = "D"

    # calculate int value of network ip
    range_start = int(ipaddress.ip_address(network_ip))
    range_end   = 0

    # parse ipv4 
    if type == "ipv4":
        
        is_reserved = not ipaddress.IPv4Network(range_start).is_global
        if is_reserved:
            return []

        range_end = range_start + int(mask) - 1
        

    # parse ipv6 
    if  type == "ipv6":

        net = ipaddress.IPv6Network(network_ip + "/" + mask)
        is_reserved = not net.is_global
        if is_reserved:
            return []
        
        range_end = int(net.broadcast_address)

    # convert registry from RIPENCC to RIPE (parser compatibilty) 
    if registry == 'RIPENCC':
        registry = "RIPE"

    # if line doesn't have any country
    if status == 'reserved' or status == "available":
        country = "ZZ"
    
    if not date:
        date = "19700101"

    return [range_start, range_end, country, registry, date, record_type]


# ==============================================================================
# Inetnum Parsing methods 

def merge_inet_files():
    
    try: 
        
        with open(MERGED_INET_FILE, "wb") as f:
            
            for inet_file in [ 
                  os.path.join(DEL_FILES_DIR, APNIC['inet_fname']), 
                  os.path.join(DEL_FILES_DIR, RIPE['inet_fname'])
                    ]:

                with open(inet_file, "rb") as source:

                    shutil.copyfileobj(source, f)

                    f.write(os.linesep.encode())
    
    except IOError as e:
        
        print(e)


# Parses merged_ine file and writes it into stripped_ine_file
def parse_inet_files_single():
    
    with open(MERGED_INET_FILE, 'r', encoding='utf-8', errors='ignore') as merged, open (STRIPPED_INET_FILE, 'w', encoding='utf-8', errors='ignore') as stripped:
        
        for group in get_inet_group(merged, "inetnum"):
            
            record = parse_inet_group(group)
            
            if record:
                line = "|".join(map(str, record))
                line = line + '\n'
                stripped.write(line)


# Returns block of data
def get_inet_group(seq, group_by):
    
    data = []
    
   
    for line in seq:
        
        # escape comments (starts with '#')
        # escape unrelevant data in ripe.inetnum (starts with '%')
        if line.startswith("#") or line.startswith("%"): 
            continue

        # every inetnum object starts with an entry -> inetnum: ...
        # so start grouping if a line starts with 'inetnum'
        # if an object has already been initialized then scann also the
        # next lines (or data) 
        if (line.startswith(group_by) or data) and not line.startswith("\n"):
            
            # don't remove spaces from description lines
            if line.startswith('descr'):
                
                line = line.replace("\n", "")
            
            else :
                
                line = line.replace(" ","").replace("\n", "")
            
            data.append(line)
            
        # note that empty lines are used as a seperator between
        # inetnum objects. So if line starts with empty line
        # then yield the data object first and then
        # reset the object to store next object's data
        elif line.startswith("\n") and data:
            yield data
            data = []



def parse_inet_files_multicore(kb = 5):

    # Fetch number of cpu cores
    cpu_cores = mp.cpu_count()

    # Clears the previous file
    if os.path.exists(STRIPPED_INET_FILE):
        file = open(STRIPPED_INET_FILE, "r+")
        file.truncate(0)
        file.close()

    # get file size and set chuck size
    filesize = os.path.getsize(MERGED_INET_FILE)
    split_size = 1024 * 1024 * kb

    # determine if it needs to be split
    if filesize > split_size:

        # create pool, initialize chunk start location (cursor)
        pool = mp.Pool(cpu_cores)
        cursor = 0
        results = []
        with open(MERGED_INET_FILE, 'r', encoding='utf-8', errors='ignore') as fh:

            # for every chunk in the file...
            for chunk in range(filesize // split_size):

                # determine where the chunk ends, is it the last one?
                if cursor + split_size > filesize:
                    end = filesize
                else:
                    end = cursor + split_size

                # seek to end of chunk and read next line to ensure you 
                # pass entire lines to the processfile function
                fh.seek(end)
                fh.readline()
                
                s = fh.readline()
                while s != '\n' and s != "":    
                    s = fh.readline()
                    #print("Chunk: ", chunk , fh.tell(), '\n', s)           


                # get current file location
                end = fh.tell()

                # print("Chunksize for chunk ",chunk,  str(end - cursor))


                # add chunk to process pool, save reference to get results
                proc = pool.apply_async(parse_inet_chunk, [MERGED_INET_FILE, cursor, end])
                results.append(proc)

                 # terminate when no more chunks are needed
                if split_size > end - cursor:
                    break
 

                #Debug
                #fh.seek(cursor)
                #lines = fh.readlines(end - cursor)  
                #print(*lines, '\n----------------------------------------\n')

                # setup next chunk
                cursor = end
               

        # close and wait for pool to finish
        pool.close()
        pool.join()

        with open(STRIPPED_INET_FILE, 'w', encoding='utf-8', errors='ignore') as parsed:
            for proc in results:
                chunk_result = proc.get()
                for entry in chunk_result:
                    entry_string = '|'.join(map(str, entry))
                    entry_string += '\n'
                    parsed.write(entry_string)


# process file chunk 
def parse_inet_chunk(file, start=0, stop=0):
    record = []
    with open(file, 'r', encoding='utf-8', errors='ignore') as inetnum_file:
        # Read only specified part of the file
        inetnum_file.seek(start)
        lines = inetnum_file.readlines(stop - start)      
        #print(*lines, '\n----------------------------------------\n')
        for group in get_inet_group(lines, "inetnum"):
            line = parse_inet_group(group)
            record.append(line)
    return record


# Parses in entry
def parse_inet_group(entry):
    
    record = {}

    # remove all empty elements in the entry
    entry = [item for item in entry if item] 
    
    # split each element (e.g. ["source:APNIC" in the entry to  ["source", "APNIC"]
    entry = [item.split(':', maxsplit = 1) for item in entry]
    
    # create a dictionary
    # if there are dupplicate items append their values ..
    # this will prevent deleting items with same key (e.g. descr)
    for item in entry:
            
            # @TODO viele Einträge mit nur einem Index
            # Warum ? -> parser-bug ? investigate ... 
            if(len(item) > 1):
                

                key = item[0]
                value = item[1].strip()
                
                if key not in record:
                    record[key] = value
                    
                # merge all descriptio entries into one 
                elif key in record and key == "descr":
                    
                    record[key] = record[key] + " " + value 
                
                # for example: in ripe.db.inetnum some ip ranges with the description 
                # "IPV4 ADDRESS BLOCK NOT MANAGED BY THE RIPE NCC" may appear -> these 
                # don't need to be parsed at all.
                # -> otherwise 5430 conflicts 
                if key == "descr":
                    if ("THIS NETWORK RANGE IS NOT ALLOCATED TO APNIC"   in value.strip().upper() or
                        "NOT ALLOCATED BY APNIC"                         in value.strip().upper() or
                        "IPV4 ADDRESS BLOCK NOT MANAGED BY THE RIPE NCC" in value.strip().upper() or
                        "TRANSFERRED TO THE ARIN REGION"                 in value.strip().upper() or
                        "TRANSFERRED TO THE RIPE REGION"                 in value.strip().upper() or
                        "EARLY REGISTRATION ADDRESSES"                   in value.strip().upper()):
                        return []
                    
                # if a country line has comment, remove the comment
                if key == "country":
                    record[key] = value.split("#")[0]

                if key == "source" and value == "ripencc":
                    record[key] = "RIPE"
            
                if key == "last-modified":
                    record[key] = value

    # extract the ranges out of record
    range = record['inetnum'].split("-")
    
    if re.match(IPV4_PATTERN, range[0]):
        
        # check if ranges are not reserved
        is_reserved = not ipaddress.IPv4Network(range[0]).is_global
        if is_reserved:
            return []

    elif re.match(IPV6_PATTERN, range[0]):
        
        # check if ranges are not reserved
        is_reserved = not ipaddress.IPv6Network(range[0]).is_global
        if is_reserved:
            return []


    range_start   = int(ipaddress.ip_address(range[0]))
    range_end     = int(ipaddress.ip_address(range[1]))
    country       = record['country']
    registry      = record['source'].split("#")[0]
    last_modified = ""
    descr         = "" 
    record_type   = "I"

    if "last-modified" in record and record["last-modified"]:
        last_modified = str(datetime.strptime(record['last-modified'], "%Y-%m-%dT%H:%M:%S%fZ")) # returns YY-MM-DD HH:MM:SS
        last_modified = last_modified.split(" ")[0]     # returns YY-MM-DD 
        last_modified = last_modified.replace("-", "")  # returns YYMMDD
    else:
        last_modified = "19700101"

    if "descr" in record:
        descr = record["descr"]

    return [range_start, range_end, country, registry, last_modified, record_type, descr]


# ==============================================================================
# Methods used for resolving conflicts/overlaps ... 


def handle_overlaps():

    # get db records
    records = read_db()

    # get all records which overlap and their corresponding indicies
    [overlaps, indicies] = extract_overlaps(records)

    # @TODO -> (delete); temporary (only for debugging) write overlap sequences into a file 
    with open(os.path.join(DEL_FILES_DIR, "overlaping"), "w", encoding='utf-8', errors='ignore') as f:
    
        for overlap_seq in overlaps:
            f.write("[\n")
            for record in overlap_seq:
                f.write(str(record))
                f.write("\n")

            f.write("]\n")

    # need to remove overlapps from the db
    delete_by_idx_from_list(records, indicies)

    # write back the clean list into db file
    write_db(records)

    # @TODO 
    # see method resolve_overlaps()
    resolve_overlaps(overlaps)

    # @TODO
    # write the clean version of records into the 
    # data base file again ...


def extract_overlaps(records):
    """
    Search for all overlaps in a list of RIA records and returns list 
    (overlaps) of lists (overlap_seq) of these overlaps. The Algorithm 
    has a complexity of O(n log(n)) known as Sweep-Line Algorithm.
    More Info: https://www.baeldung.com/cs/finding-all-overlapping-intervals    

    Arguments
    ----------
    records: list 
        List of RIA entries with the follwoing format:
        [ 
          ...
          [ip_from, ip_to, cc, registry, last-modified, record_type, description],
          ...
        ]

    Returns
    ----------
    overlaps: list
        List of lists. Represents all found overlaps
        Each entry of overlap_seq have the following format: 
            [ 
              ...
              [ip_from, ip_to, cc, ....]
              ...
            ]
        
        indicies: list
            contains indicies of overlapped records

    """

    # if list is empty return 
    if not records:
        return 

    P = [] 
    currentOpen = -1
    added = False
    overlap_seq = []
    overlap_indicies = []
    overlaps = []
    overlaps_nr = 0

    for i in range(len(records)):
        P.append([records[i][0], "L", i, records[i]])
        P.append([records[i][1], "R", i, records[i]])

    P.sort()


    for i in range(len(P)):
    
        if P[i][1] == "L":
            if currentOpen == -1:
                currentOpen = P[i][2]
                added = False
            else:
                index = P[i][2]
                overlap_seq.append(records[index])
                overlap_indicies.append(index)
                overlaps_nr = overlaps_nr + 1
                if not added:
                    overlap_seq.append(records[currentOpen])
                    overlap_indicies.append(currentOpen)
                    added = True
                    overlaps_nr = overlaps_nr + 1
                if records[index][1] > records[currentOpen][1]:
                    currentOpen = index
                    added = True
        else:
            if P[i][2] == currentOpen:
                currentOpen = -1
                added = False
                overlaps.append(overlap_seq)
                overlap_seq = []

    # remove empty sequences
    overlaps = [overlap_seq for overlap_seq in overlaps if overlap_seq] 
    
    overlaps.sort(key=lambda seq: len(seq))

    print(f"overlaps found {overlaps_nr}\n")

    return [overlaps, overlap_indicies]


def resolve_overlaps(overlaps):

    overlaps_tmp = [] 
    
    # need to solve overlaps for each overalp sequence .... 
    # as long as ther are overlaps in the sequence ->  complexity O(n²)
    for overlap_seq in overlaps:

        #while(records_overlaps(overlap_seq)):

            overlap_seq = [resolve_overlaps_helper(overlap_seq)]

            overlaps_tmp.extend(overlap_seq)    


    # @TODO -> (delete); temporary (only for debugging) write overlap sequences after removing overlapps 
    with open(os.path.join(DEL_FILES_DIR, "overlaping_left"), "w", encoding='utf-8', errors='ignore') as left, open(os.path.join(DEL_FILES_DIR, "overlaping_solved"), "w", encoding='utf-8', errors='ignore') as solved:
        
        nr_overlaps = 0
        for overlap_seq in overlaps_tmp:
            
            if(records_overlaps(overlap_seq)):

                left.write("[\n")
                
                for record in overlap_seq:
                    nr_overlaps = nr_overlaps + 1 
                    left.write(str(record))
                    left.write("\n")

                left.write("]\n")
            
            else:

                solved.write("[\n")
                
                for record in overlap_seq:
                    solved.write(str(record))
                    solved.write("\n")

                solved.write("]\n")
            
        print(f"overlaps left {nr_overlaps}")
        

def resolve_overlaps_helper(overlap_seq):
    
    records = []

    for i in range(len(overlap_seq)-1):

        if (overlap_seq[i][0] == overlap_seq[i+1][0] and
           overlap_seq[i][1] == overlap_seq[i+1][1]):

            if(overlap_seq[i][3] == overlap_seq[i+1][3]):

                # @TODO take inetnum. Current approach take first one 
                records.append(overlap_seq[i])

            else :
                # @TODO ...
                records.append(overlap_seq[i+1])

        else:
            # @TODO ...
            records.append(overlap_seq[i])

    return records


def records_overlaps(records):
    """
    Checks if any two records overlaps in the given list of RIA records 
    Note that complexity  O(n log(n))

    Arguments
    ----------
    records: list 
        List of RIA entries with the follwoing format:
        [ 
          ...
          [ip_from, ip_to, cc, registry, last-modified, record_type, description],
          ...
        ]

    Returns
    ----------
    boolean value
        if there is any overlap in the given list

    """

    # if list is empty return
    if not records:
        return 
      
    P = [] 

    for i in range(len(records)):
        P.append([records[i][0], "L", i])
        P.append([records[i][1], "R", i])
        
    P.sort()

    for i in range(len(P)-1):
    

        if P[i][1] == "L" and P[i+1][1] != "R":
            return True
        
    return False



# ==============================================================================
# Help Methods used for all files ... 


def merge_stripped_files():
    
    try: 
        
        # merges the stripped files into a one file (final database)
        with open(IP2COUNTRY_DB, "wb") as f:
            
            for del_file in [ 
                    os.path.join(STRIPPED_DEL_FILE), 
                    os.path.join(STRIPPED_INET_FILE),
                    ]:

                with open(del_file, "rb") as source:

                    shutil.copyfileobj(source, f)

                    f.write(os.linesep.encode())
 
    except IOError as e:
        
        print(e)


def sort_file(file=IP2COUNTRY_DB):

    records = []

    # get records from final db
    records = read_db(file)

    # sort this list
    records.sort()

    # write sorted list back into final db
    write_db(records)


def delete_temp_files():
    os.remove(MERGED_DEL_FILE)
    os.remove(STRIPPED_DEL_FILE)
    os.remove(MERGED_INET_FILE)
    os.remove(STRIPPED_INET_FILE)


## ==============================================================================
## Parser Entry Method 


def run_parser():

    start_time = time.time()
    print("parsing started\n")

    # print("parsing del files ...")
    #merge_del_files()          
    #parse_del_files()           
    
    # print("parsing inetnum files ...")
    #merge_inet_files()
    #parse_inet_files_single()
    #parse_inet_files_multicore()

    merge_stripped_files()
    
    print("resolving overlaps ...")
    handle_overlaps()

    # delete_temp_files()
    print("finished\n")

    end_time = time.time()
    print("total time needed was:", f'{end_time - start_time:.3f}', "s\n") 
    
    return 0


# Needed if for multiprocessing not to crash
if __name__ == "__main__":   
     run_parser()


