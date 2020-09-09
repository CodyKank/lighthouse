#!/usr/bin/env python3


import subprocess, urllib.request, os.path

class User:
    """Represenatation and collection of functions for a CRC User."""

    # Add pwd object?

    def __init__(self,user_name=None, real_name=None):
        """Initialize a user given a user name"""

        self.user_name = user_name
        self.real_name = real_name
        self.job_list = []
        self.num_jobs = None
        self.condor_jobs = None
        self.user_lists = []
        self.host_groups = []

        if not real_name:
            # Grabbing the user's real name
            self.real_name = subprocess.check_output(["/usr/bin/grep {0} /etc/passwd | cut -d: -f5".format(self.user_name)],shell=True).decode("utf-8").strip()

    def get_jobs(self):
        """Retrieve UGE jobs for user."""

        # Delete any previous jobs since we search for every single one anyways.

        self.job_list = []

        # Check to be sure user has a name
        if self.user_name == None:
            return

        # Obtain all jobs for this user.
        qstat = subprocess.check_output(["/opt/sge/bin/lx-amd64/qstat -u {0}".format(self.user_name)],shell=True).decode("utf-8").split("\n")
        # Grabbing a slice of qstat, don't want first 2 lines nor the last line.
        jobs = qstat[2:len(qstat) -1 ]

        for job in jobs:
            # Forcing a job into a list of its parts.
            split_job = job.split()
            if split_job[4] == "r" or split_job[4] == "Rr":
                # Manipulate the string queue@hostname.crc.nd.edu to grab the queue and the hostname itself
                queue_at_host = split_job[7]
                queue = queue_at_host[:queue_at_host.find("@")]
                host = queue_at_host[queue_at_host.find("@")+1:]

                user_job = Job(split_job[0],split_job[2],split_job[3],split_job[4],host,queue)
            else:
                user_job = Job(split_job[0],split_job[2],split_job[3],split_job[4])

            self.job_list.append(user_job)

        self.num_jobs = len(self.job_list)
        return

    def get_ul(self):
        """Find the user lists this user is a part of.
        This will run a helper bash script, get_user_lists.sh. Otherwise it
        would be too cumbersome to query for the usersets.
        
        Once the helper grabs all usersets, search through each one and place as a list the 
        user-sets this user is a part of within self.user_lists as a list of strings.
        
        This function is a heavy hitter and will take awhile to process."""

        subprocess.call("./get_user_lists.sh", shell=True) # Places every user list into a file, ~/.lighthouse/user_lists/all_userset.txt

        # Separate file into a dict

        all_userset = ""
        cache_loc = os.path.expanduser("~/.lighthouse/user_lists/all_userset.txt")

        if os.path.isfile(cache_loc):
            with open(cache_loc, 'r') as cache_file:
                all_userset = cache_file.read()
        else:
            # Something went wrong, may want to raise a warning here.
            return

        split_userset = all_userset.split("==>")[1:]

        all_userset_dict = {}

        # Process each user set into a dict with key as name and values as a list of users in that userset.
        for userset in split_userset:
            if (len(userset) < 12):
                # Something went wrong or userset has no users
                continue
            expanded_userset = userset.split()
            userset_name = os.path.basename(expanded_userset[0])
            ul_users = userset.split()[11:]

            if len(ul_users) == 1:
                all_userset_dict[userset_name] = ul_users[0].split(",")
            else:
                # Remove all occurence of "\\"
                clean_ul = list(filter(("\\").__ne__, ul_users))
                all_userset_dict[userset_name]  = "".join(ul_users).split(",")

        # Now we have a dictionary of all usersets with key == userset name and values == list of users.
        for key in all_userset_dict:
            if self.user_name in all_userset_dict[key]:
                self.user_lists.append(key)
        return
    
    def get_host_groups(self):
        """Using usersets find what hostgroups user has access to."""

        # If I don't have any user-sets, possible it hasn't been ran.
        if (len(self.user_lists) == 0):
            self.get_ul()

        # loop below over long, gpu, gpu-debug, hpc, and hpc-debug

        for queue in ["long","gpu","gpu-debug","hpc","hpc-debug"]:
       
            sq = subprocess.getoutput("qconf -sq {0}".format(queue))
            
            #splicing the sq output up to the user_list point, we don't need the rest of the garbarge before that
            sq = sq[sq.find('user_lists') + 9 :sq.find('xuser')]
            sq = (((sq.replace('\n', '')).replace(' ', '')).replace('\\', '')).replace('],', '')
            host_user_list = []
            sq = sq.split('[')
            hostg_list = []
            for line in sq:
                if line.find('@') != (-1):
                    #host-groups in sq output have '@', so that's what we're looking for
                    hostg_list.append(line)
            for line in hostg_list:
                for ul in self.user_lists:
                    if ul in line:
                        self.host_groups.append(Hostgroup(line.split('=')[0],queue))

        self.host_groups.sort()
        return


class Job:
    """Representation and collection of functions for a CRC Job"""

    def __init__(self,jobID = None, name=None,user=None,exec_host=None,status=None,queue=None):
        """Initialize a grid engine Job.

        :param jobID:     String, the grid engine internal JobID.
        :param name:      String, whatever the user named this job.
        :param user:      String, the user who owns this job in grid engine.
        :param status:    String, the status of the job according to UGE.
        :param exec_host: String, Which machine this job is running on (if it is).
        :param queue:     String, which queue this job is running in.

        host_top:         String of header to top command from Xymon.
        details:          Dictionary, contains details for this job.
        """

        self.job_id = jobID
        self.name = name
        self.user = user
        self.status = status
        self.exec_host = exec_host # This needs to become it's own class
        self.host_top = None
        self.queue = queue
        self.detail_cache = False
        self.details = []

    def __str__(self):
        """String representation of a job, just spit out the jobID."""

        return str(self.name)

    def get_details(self):
        """Retrieve details on job from Xymon.

        :return: Nothing, mutates job.details.
        """

        full_page = urllib.request.urlopen("https://mon.crc.nd.edu/xymon-cgi/svcstatus.sh?HOST={0}&SERVICE=cpu".format(self.exec_host))
        pageStr = full_page.read().decode("utf-8") # getting all html into a string
        full_page.close()
        del full_page

        # Grabbing the first 5 lines as one single string for $(top) header
        self.host_top = "\n".join(pageStr.split('\n')[0:5])
        # Each line below will be a line in Top for processes
        top_bool = True
        for index, line  in enumerate(pageStr.split('\n')):
            if top_bool:
                if "load average" in line:
                    top_bool = False
                    top_index = index
                
            if self.user in line:
                tmp_proc = {}
                lineSplit = line.split()
                tmp_proc["PID"] = lineSplit[0]
                tmp_proc["RESMEM"] = lineSplit[5]
                tmp_proc["CPU%"] = lineSplit[8]
                tmp_proc["TIME"] = lineSplit[10]
                tmp_proc["PNAME"] = lineSplit[11]
                self.details.append(tmp_proc)

        self.host_top = "\n".join(pageStr.split('\n')[top_index:(top_index + 5)])

        return


class Hostgroup:
    """Representation of a hostgroup as defined in UGE."""

    def __init__(self,name,queue=None,node_list=None):
        """Intialize a Hostgroup object.

        :param queue: String to indicate which queue this HG belongs in, i.e. Long, GPU, etc. Defaults to None.
        :param node_list: A list of Node objects for each node within this hostgroup. Note that HGs can nest...Default to None.
        """

        # If "@" isn't in the name toss it in there.
        if not("@" in name):
            name = "@" + name

        self.name = name
        self.queue = queue
        self.job_list = []
        if node_list:
            self.node_list = node_list
        else:
            self.node_list = []
        self.total_cores = 0
        self.used_cores = 0
        self.free_cores = 0
        self.disabled_cores = 0
        self.disabled_nodes = 0
        self.total_jobs = None
        self.filled = False

    def __lt__(self, other_hg):
        """Overloading "<" for python sort function."""

        if self.name < other_hg.name:
            return True
        else:
            return False

    def get_nodes(self):
        """Obtain a list of nodes as Node objects which belong to this hostgroup. Does not care about nesting."""

        # Checking if node_list has already been found, if so don't do it again.

        if not(self.node_list):
            nl = subprocess.check_output("qconf -shgrp_resolved {0}".format(self.name), shell=True).decode("utf-8").split()

            for node in nl:
                self.node_list.append(Node(node))

        return

    def get_jobs(self):
        """Obtain a list of jobs running on this host group. Cannot look for queued Jobs!"""

        # Checking if cached. If desire to overwrite cache set this to false before calling
        if self.filled == True:
            return

        if not(self.node_list):
            self.get_nodes()

        running_str = subprocess.check_output("qstat -q {0}@{1} ".format(self.queue,self.name) + "| tail -n +3 | awk '{if ($5==\"r\" || $5==\"Rr\") print $0}'",\
                shell=True).decode("utf-8")

        job_list = []

        if running_str:

            for job in running_str.split("\n"):
                # Create job objects for each of these. Store in self.job_list. Replace the current job_list.
                split_job = job.split()

                # Something possibly went wrong.
                if not split_job:
                    continue

                job_id = split_job[0]
                job_name = split_job[2]
                job_user = split_job[3]
                job_exec_host = split_job[7][split_job[7].index("@") + 1 :]
                job_list.append(Job(job_id,job_name,job_user,job_exec_host))
            self.job_list = job_list


        # Now obtain the job totals for this HG and the # of used cores etc.

        self.total_jobs = len(self.job_list)

        qstat_str = subprocess.check_output("qstat -f -q {0}@{1}".format(self.queue,self.name),shell=True).decode("utf-8")

        split_qstat = qstat_str.split("---------------------------------------------------------------------------------")[1:]
        # Trimming off pending jobs
        split_qstat[-1] = split_qstat[-1].split("\n\n###############################################################################")[0]

        self.disabled_cores = 0
        self.disabled_nodes = 0
        self.total_cores = 0
        self.used_cores = 0
        self.free_cores = 0

        for node in split_qstat:
            # find totals, check if it's disabled.
            strip_node = node.strip()
            split_node = strip_node.split()
            core_list = split_node[2].split("/") # 0/used/total
            if len(split_node) >= 6:
                if split_node[5]  == "adu" or split_node[5] == "E" or split_node[5] == "d" or split_node[5] == "Ed":
                    # In some sort of error / disabled.
                    self.disabled_nodes += 1
                    self.disabled_cores += int(core_list[-1])
                    self.total_cores += int(core_list[-1])
                else:
                    self.total_cores += int(core_list[-1])
                    self.used_cores += int(core_list[1])
            else:
                self.total_cores += int(core_list[-1])

        self.free_cores = self.total_cores - self.used_cores - self.disabled_cores

        self.filled = True
        return


class Node:
    """Representation of a Node object within the CRC. Contains information from UGE and Xymon."""

    def __init__(self,name,details=None,job_list=None):
        """Initialize a Node object.

        :param name: String for the name of this node.
        :param details: String holding Xymon's $(top) of this node. Defaults to None.
        :param job_list: List of jobs running on this node according to UGE, stored a Job objects. Defaults to None.

        job_cached: Boolean used to determine if we should refresh the job_list of not.
        total_cores: How many cores this node has.
        used_cores: How many cores are reserved according to UGE.
        disabled: Boolean to show whether or not this node is disabled or alarm state.
        total_mem: String, how much memory this node has (approx)
        free_mem: String, how much memory is free on this node (approx)
        used_mem: String, how much memory is used on this node (approx)

        """

        self.name = name
        self.details = None
        self.total_cores = None
        self.used_cores = None
        self.free_cores = None
        self.total_mem = None
        self.used_mem = None
        self.free_mem = None
        self.job_list = None
        self.num_jobs = None # len(job_list)
        self.job_cached = False
        self.disabled = False


    def get_details(self):
        """Obtain and Parse through a Xymon $(top) for this node."""

        # Not implemented yet, stub

        pass

    def get_jobs(self):
        """Obtain which jobs are on this node."""

        # Not implemented yet, stub
        pass


