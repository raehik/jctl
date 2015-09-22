Notes
-----

  * Requires [ezstring][].

[ezstring]: https://github.com/raehik/scripts


Commands
--------

```
jctl new/n Title here, without quotes
jctl new-electronic/ne Title etc.
jctl new-scan/ns Title etc.

jctl search/f "Title keywords" [entries to search e.g. 2014-*]...
jctl edit/e "Title keywords" [search entries]...
jctl commit/c ["Commit message"] [-f {file to commit} -m {commit msg for specified file}]...
jctl status/s
jctl push/p (even needed?)
```


### Commit

```python
if len(newfiles) == 0:
    exit_with_msg("Nothing to commit", 1)

if sys.argc == 0:
    if len(newfiles) == 1:
        # exactly 1 file to commit & no args provided, so automate it
        file = newfile
        commit_msg = "%s: new entry" % file
    else:
        # more than 1 file -- need to specify which one(s) to commit
        exit_with_msg("More than one file to commit. Specify file with -f and message for previous file with -m", 2)

# else we then start checking optparse stuff...

#if len(newfiles) > 1, require at least 1 -f + -m option pair
#if len(newfiles) = 1, -f + -m is optional (but if wrong, error out)
```


Search
------

```
if sys.argc = 0:
    exit_with_msg("No search terms given (expected at least 1 argument)", 1)
elif sys.argc = 1:
    searchlist = posts
else: # sys.argc > 1
    searchlist = sys.argv[1:] # remove 1st arg (= search terms)

search_term = $(ezstring "sys.argv[0]") # basically
```
