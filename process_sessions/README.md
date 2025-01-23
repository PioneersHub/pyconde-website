
# Website Schedule

Based on data from pretalx build and manage corresponding pages for the website.

Session pages are located in `content/program/<PRETALX_SESSION_ID>`

PRETALX_SESSION_ID is the id for the submission accepted.

## Preparation:
Load talk data from pretalx. 
Filter all session with status and `confirmed`.

1. Create a list of all directories: [PRETALX_SESSION_ID, PRETALX_SESSION_ID,...]
2. Remove for all (set("list of all directories") - set("filtered session ids from pretalx")): 
 PRETALX_SESSION_ID/contents.lr if PRETALX_SESSION_ID is no longer in sessions (session canceled).
3. For all "filtered session ids from pretalx":
 Update Pages with current contents from pretalx,  
 if not exists: create directory `PRETALX_SESSION_ID/`. Add `contents.lr` built with `/process_sessions/session_template.py` template.

## Session Pages

[Example Page](https://2022.pycon.de/program/EMNPJW/)

`/process_sessions/session_template.py` template to generate the `contents.lr` file.

The data fields are defined in `models/session.ini`.

The webpage template is `templates/session.html`. This is the hacky Jinja2 part if the website needs to be altered.

### To Dos / Updates
The template uses format strings, the elements need to be renamed due to the switch from G-Sheet to Pretalx.

Some information might not be available, yet (room, time). MAke sure the Jinja2 template can handle missing data (i.e. does not display anything there)

## Session List

[Example Page](https://2022.pycon.de/program/)

## Schedule Table

[Example Page](https://2022.pycon.de/schedule-full-table/)

## Schedule Table Transposed

[Example Page](https://2022.pycon.de/scheduleT/)

## Sessions by Categories (Filter)

Similar 

### Tutorial Session List

[Example Page](https://2022.pycon.de/program/categories/tutorial/)


### Talk Session List

[Example Page](https://2022.pycon.de/program/categories/talk/)


### PyCon Session List

[Example Page](https://2022.pycon.de/program/categories/pycon/)


### PyData Session List

[Example Page](https://2022.pycon.de/program/categories/pydata/)


### General Session List

[Example Page](https://2022.pycon.de/program/categories/general/)


### Testing it!

To test everything locally, add within `databags/links.json` the product `Program` accordingly. Just
check in the git history how it was last time when the program was released.
