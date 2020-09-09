#!/bin/env python3

import subprocess, sys, time, pwd
from dialog import Dialog
from os import system, environ
from crc_user import User

"""
Front End to nodeSearch for pretty use with pythondialog. 
"""

USER = environ['USER']
F_NAME = subprocess.check_output(["/usr/bin/grep {0} /etc/passwd | cut -d: -f5 | cut -d\" \" -f1".format(USER)],shell=True).decode("utf-8").strip()
HOME = environ['HOME']
JOB_CACHE = False
HG_CACHE = False

def main(dialog=None):
    """Main function for lighthouse. Create dialog box and accept input."""

    exit_cond = False

    # This is the default user, we are assuming we are wanting to check whoever
    # is running this script.
    my_user = User(USER,F_NAME)

    d = Dialog(dialog="dialog") # creating the inital dialog object
    d.set_background_title("LightHouse")
    disp_warning(d)

    while(not(exit_cond)):

        resp, tag = d.menu("Hello {0}, what would you like to see?".format(F_NAME),
                choices=[("(1)", "My Jobs."),
                        ("(2)", "My Resources."),
                        ("(3)", "My Available Storage."),
                        ("(4)", "Search")],
                        cancel_label="Quit",
                        ok_label="Select"
                    )

        # If user quits
        if resp == d.CANCEL:
            d.infobox("Goodbye.")
            time.sleep(1)
            exit_cond = True

        if tag:
            if tag == "(1)":
                exit_cond = handle_jobs(d,my_user,True)
            elif tag == "(2)":
                exit_cond = handle_resources(d,my_user,True)
            elif tag == "(3)":
                exit_cond = handle_storage(d,my_user,True)
            elif tag == "(4)":
                exit_cond = handle_search(d)
            else:
                death_window(d)

    # Uncomment when not debugging
    system("clear")
#^----------------------------------------------------------------------- main()


def disp_warning(d):
    """Display a warning about lack of stability in this program.

    :param d: Dialog object.
    :return: Nothing, prints window to screeen and returns to main.
    """

    lighthouse_str = """
        ____                                     
        |\/| *************************************
        ----   ***********************************
        |..|     __    _       __    __  __  __                    
        |..|    / /   (_)___ _/ /_  / /_/ / / /___  __  __________ 
        |..|   / /   / / __ `/ __ \/ __/ /_/ / __ \/ / / / ___/ _ \\
        |..|  / /___/ / /_/ / / / / /_/ __  / /_/ / /_/ (__  )  __/
        |..| /_____/_/\__, /_/ /_/\__/_/ /_/\____/\__,_/____/\___/ 
        |..|         /____/                                        
        \n\nNOTE: This is a prototype. Expect bugs and ugliness.
        """

    d.scrollbox(lighthouse_str,
            title="Welcome",
            exit_label="Continue")
#^-------------------------------------------------------------- disp_warning(d)


def handle_jobs(d,user,isme=True):
    """Find and display options for the user's jobs.

    Obtain information about a user's Grid engine job in either fine grain or
    coarse grain. Also search for HTCondor jobs on this specific host.
    Utilizes node_search for specifics.

    :param d: Dialog object. 
    :param user: User Object, repr of the user we are basing our search on.
    :param isme: Bool, signify if it's the true user using this or searching for other.

    :return: Bool, whether or not to exit main loop.
    """

    job_bool = True
    ret_bool = False
    global JOB_CACHE

    while job_bool:

    # Add ability to refresh if not first time here...
        if not JOB_CACHE:
            d.infobox("Searching for Jobs....")
            # Executing class function to find and obtain basics on user's job(s).
            user.get_jobs()

        if user.num_jobs == 0:
            if isme:
                d.infobox("\nYou do not have any jobs\nsubmitted at this time.")
            else:
                d.infobox("\n{0} does not have any jobs\nsubmitted at this time.".format(user.user_name))
            time.sleep(2)
            ret_bool = False
            break

        # Now we have a basic list of jobs in user.job_list, display that to user.

        if isme:
            disp_str = "You have {0} total UGE job(s). ".format(user.num_jobs)
        else:
            disp_str = "{0} has {1} total UGE job(s). ".format(user.user_name,user.num_jobs)

        # Find any pending and running jobs.
        
        # Creating a list of tuples, (JobID, Job-Name) for user to select from.
        # If there are any pending jobs, add pending jobs as an option to see.
        choice_tuples = []
        pending_list = []
        for job in user.job_list: # Change this to running list when able to
            if job.status == "r" or job.status == "Rr" or job.status == "T":
                choice_tuples.append((job.job_id, job.name))
            else:
                pending_list.append((job.job_id, job.name))

        if pending_list:
            disp_str += "\n{0} are running, {1} are waiting in queue.\n".format(str(len(choice_tuples)),str(len(pending_list)))
            choice_tuples.append(("NA", "Pending Jobs"))
        else:
            disp_str += "\nAll jobs submitted are running.\n"


        resp, tag = d.menu(disp_str,
                title="UGE Jobs",
                choices=choice_tuples,
                        cancel_label="Back",
                        ok_label="Select",
                        extra_button=True,
                        extra_label="Refresh"
                    )
        # We want to refresh the job list.
        if resp == d.EXTRA:
            JOB_CACHE=False
            # Head back to beginning of loop.
            continue 
        # If user selected "Back".
        elif resp == d.CANCEL:
            JOB_CACHE = True
            # Break out of handle_jobs
            job_bool = False

        elif resp == d.OK:
            # Tag will contain the jobID of the selected job. Get detailed view.
            JOB_CACHE = True
            if tag != "NA":
                show_job_details(d, user, tag)
            # This means user selected pending jobs, show them list of pending jobs.
            elif tag == "NA":
                show_pending(d, user, pending_list)

        else:
            job_bool = False
    

    return ret_bool
#^--------------------------------------------------------------- handle_jobs(d)


def show_job_details(d, user, job_id):
    """Show job details in terms of processes running etc from Xymon.

    :param d: dialog object.
    :param user: User object, the user we are inspecting.
    :param job_id: String, the jobId the user selected to view.
    :return: Nothing, go back to job list in handle_jobs.
    """
    refresh_bool = True

    while refresh_bool:

        # Find which job in user.job_list job_id is
        for index, job in enumerate(user.job_list):
            if job.job_id == job_id:
                break
            else:
                index = -1


        # If we don't find this jobID, something went wrong. Die.
        if index == -1:
            print("Error: Cannot find JobID selected in list of jobs...Dying.")
            death_window(d)

        # See if we need to grab details or not.
        if not job.detail_cache:
            d.infobox("Obtaining details of job {0}...".format(job_id))
            user.job_list[index].get_details()
            job.detail_cache = True


        # Construct the detail string to display from details dict.

        title_str = "{0}-{1} Details".format(job_id, job.name) 
        disp_str = "Press TAB to choose between Back and Refresh. Host details:\n" +\
                "\n" + "Node: {0}.\n".format(job.exec_host) + \
                job.host_top + "\n\nJob's processes:\n\n"

        disp_str += """
   PID        Process Name      Mem Usage     CPU%      Time   
  ------      ------------      ---------     ----      ----\n"""
        

        # Run through each process and add it to the disp_str.
        for proc in job.details:
            disp_str += " ".center(2)  + str(proc["PID"]).center(6) + " ".center(6) + proc["PNAME"].center(12) + \
                    " ".center(6) + proc["RESMEM"].center(9) + " ".center(5) + proc["CPU%"].center(4) + \
                    " ".center(3) + proc["TIME"] + "\n"

        # Display job details in a scroll-able box.
        # Show option to refresh details with the "extra" button.
        code = d.scrollbox(disp_str,
                title=title_str,
                ok_label="Back",
                extra_button=True,
                extra_label="Refresh")
        if code == d.EXTRA:
            job.detail_cache = False
            refresh_bool = True
        else:
            job.detail_cache = True
            refresh_bool = False


    return
#^-------------------------------------------- show_job_details(d, user, job_id)


def show_pending(d,user,pending_list):
    """Display the list of pending jobs for this user.

    :param d: Dialog object for this screen.
    :param user: User Object for the user we are searching for.
    :param pending_list: List, collection of pending jobs for user.
    :return: Nothing, go back to list of jobs.
    """

    pending_loop = True

    while pending_loop:

        # Show list of pending jobs, then when one is selected go to details page of job.

        resp, tag = d.menu("Which Pending Job would you like to see?",
                choices=pending_list,
                        cancel_label="Back",
                        ok_label="Select",
                        title="Pending Jobs"
                    )

        if resp == d.CANCEL:
            # Break out of this loop, move on.
            pending_loop = False
        elif resp == d.OK:
            # Show detail landing page for job.
            d.infobox("I haven't implemented this yet\nI'm sorry...\n    :(",title="WARNING -- NOT IMPLEMENTED")
            time.sleep(2)
            pass
            

    return
#^------------------------------------------ show_pending(d, user, pending_list)


def handle_resources(d,user,isme):
    """Search for and display resources available to the specified user.

    :param d: Dialog object.
    :param user: User object for whom we are searching for.
    :return: Bool, True if we should break main loop or False to continue.
    """
    d.infobox("This is under construction.\n\nExpect delays and errors.\n",title="WARNING -- UNDER CONSTRUCTION")
    time.sleep(2)

    loop_bool = True
    global HG_CACHE

    while loop_bool:


        if not HG_CACHE:
            d.infobox("Gathering list of resources...           \n\nThis may take some time.\n",title="Host-group Search")

            # obtaining the list of user-lists this user is a part of. Will be stored at user.user_lists (list of strings)
            user.get_ul()

            # Before continuing check if user is in accessdeny, if so throw warning to user and no need to finish.

            # Grab information on hostgroups, get which user sets have access to them
            user.get_host_groups()
            HG_CACHE = True

        disp_list = []
        if isme:
            title_str = "My Resources"
            menu_str = "Host groups I have access to."
        else:
            title_str = "{0}'s Resources".format(user.user_name)
            menu_str = "Host groups {0} has access to.".format(user.user_name)


        for index, hg in enumerate(user.host_groups,start=1):
            disp_list.append(("({0})".format(str(index)), hg.name))

        
        resp, tag = d.menu(menu_str + "\nSelect one for more information.",
                choices=disp_list,
                        cancel_label="Back",
                        ok_label="Select",
                        title=title_str
                    )

        if resp == d.CANCEL:
            loop_bool = False
        elif resp == d.OK:
            host_group_details(d,user,tag,isme)


    return False
#^----------------------------------------------------- handle_resources(d,user)

def host_group_details(d,user,tag,isme):
    """Show details of a host group.

    :param d: Dialog object
    :param user: User object, the user whom we were originally searcing
    :param tag: Which number in the HG list in user.host_groups the user selected
    :param isme: Boolean whether or not this user we searched is the executioner or another user.

    :returns: Nothing.
    """

    d.infobox("Gathering host group information...\n",title="HG Search")

    host_group = user.host_groups[int(tag.replace("(","").replace(")","")) - 1]

    loop_bool = True

    while loop_bool:

        host_group.get_nodes()

        host_group.get_jobs()

        disp_str = "Information pertaining to {0}.\n".format(host_group.name)

        disp_str += "{0} Total Nodes.\n{1} Disabled Nodes.\n{2} Total jobs running.\n".format(str(len(host_group.node_list)),\
                str(host_group.disabled_nodes),str(len(host_group.job_list)))

        disp_str += "{0} Total Cores.\n{1} Cores Used.\n{2} Cores Free.\n \n{3} Disabled Cores".format(str(host_group.total_cores),\
                str(host_group.used_cores),str(host_group.free_cores),str(host_group.disabled_cores))

        title_str = host_group.name

        disp_list = []

        for index, node in enumerate(host_group.node_list, start=1):
            disp_list.append(("({0})".format(str(index)),"{0}".format(node.name)))

        resp, tag = d.menu(disp_str + "\nSelect a Node for more information.",
                choices=disp_list,
                        cancel_label="Back",
                        ok_label="Select",
                        title=title_str,
                        height=25
                    )

        if resp == d.CANCEL:
            loop_bool = False
        elif resp == d.OK:
            inspect_node(d,host_group.node_list[int(tag.replace("(","").replace(")","")) - 1])

    return
#^-------------------------------------------host_group_details(d,user,tag,isme)

def inspect_node(d,node):
    """View details of a node. Show the UGE jobs on this node along with a $(top) from xymon.
    
    :param d: Dialog object.
    :param node: Node object, the node we want to display details of.
    """

    d.infobox("I haven't implemented this yet\nI'm sorry...\n    :(")
    time.sleep(2)



    pass

def handle_storage(d,user,isme):

    d.infobox("I haven't implemented this yet\nI'm sorry...\n    :(")
    time.sleep(2)

    pass
#^------------------------------------------------------- handle_storage(d,user)

def handle_search(d):
    """Search for a different user other than yourself. Accept a text input
    and feed to the other fuctions.

    :param d: Dialog object.
    :return: Bool, True if we should break main loop or False to continue.
    """

    search_bool = True

    # Accept a user name. Eventually, accept any name and look for possible
    # matches in /etc/passwd and display.

    while search_bool:

        code, user_name = d.inputbox("Who would you like to search for?",
                cancel_label="Back")

        if code == d.CANCEL:
            return False
        elif code == d.OK:
            # Verify user-name
            # Need to verify with pwd,  foo = pwd.getpwnam("ckankel")
            try:
                user_pwd = pwd.getpwnam(user_name)
            except KeyError:
                d.infobox("I couldn't find {0} as a user...\nCheck spelling and try again.".format(user_name))
                time.sleep(2)
                continue

            search_bool = False
            # Creating a new user object for the user we are searching for.
            search_user = User(user_name)
            search_landing(d,search_user)
        
    return False
#^------------------------------------------------------------- handle_search(d)

def search_landing(d, user):
    """Prompting user what to search for with new user-name.

    :param d: Dialog object we are casting the screen with.
    :param user: User object containing user we want to search for.
    :return: Nothing.
    """

    # Create a menu similiar to the one in main().
    # Obtain bools from the individual functions whether or not to break from here.
    exit_loop = False
    global JOB_CACHE
    global HG_CACHE

    # Set JOB_CACHE to false, otherwise if we searched for ourselves earlier it will
    # royally screw this up here.
    JOB_CACHE = False
    HG_CACHE = False

    while (not(exit_loop)):

        resp, tag = d.menu("What would you like to see for {0}?".format(user.user_name),
                choices=[("(1)", "Jobs."),
                        ("(2)", "Resources."),
                        ("(3)", "Available Storage.")],
                        cancel_label="Back",
                        ok_label="Select",
                        title="User Search"
                    )

        if resp == d.CANCEL:
            exit_loop = True
        elif resp == d.OK:
            # Execute a function depending on which tag was selected.
            if tag:
                if tag == "(1)":
                    exit_loop = handle_jobs(d,user,False)
                elif tag == "(2)":
                    exit_loop = handle_resources(d,user,False)
                elif tag == "(3)":
                    exit_loop = handle_storage(d,user,False)
                else:
                    death_window(d)


    return
#^------------------------------------------------------- search_landing(d,user)


def death_window(d):
    """Display a warning window and die.

    :param d: Dialog display object.
    :return: Nothing, execution will halt.
    """

    d.infobox("Unexpected Error occured. I am exiting. . .")
    time.sleep(5)
    sys.exit(1)
#^-------------------------------------------------------------- death_window(d)


if __name__ == "__main__":

    main()
