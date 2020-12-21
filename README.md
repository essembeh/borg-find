# borg-find

*borg-find* is a command line tool to search and manipulate files from *archives* inside [Borg](https://borgbackup.readthedocs.io) *repositories*.


[Borg](https://borgbackup.readthedocs.io) is a fantastic tool to manage your backups, I've been using it for years for personal and professional needs.
Recently I was lacking some *bisect*-like command, to iterate over hundreds of *archives* searching when a specific file changed.
The basic *borg* commands are quite limited to do that, so I started developping scripts and ended up with this project.



# Install

Install from [PyPI](https://pypi.org/borg-find)
```sh
$ pip3 install --user -U borg-find
```


To install from the sources, ensure you have [Poetry](https://python-poetry.org) installed
```sh
$ pip3 install --user -U poetry
```

Clone the project
```sh
$ git clone https://github.com/essembeh/borg-find
$ cd borg-find
```

To setup the *virtualenv*:
```sh
$ poetry install # to install app with dev dependencies
$ poetry install --no-dev # to install app without dev depdencies
$ poetry shell
(venv) $ borg-find --help
```

To run the app:
```sh
$ poetry run borg-find --help
```

# Usage

```
usage: borg-find [-h] [--version] [-v] [-A YYYY-MM-DD] [-B YYYY-MM-DD]
                 [-P PREFIX] [-R] [-F N | -L N] [-n MOTIF] [-r PATTERN]
                 [--new] [--modified] [-x EXEC | --md5 | --sha1 | -o FOLDER]
                 [repository]

positional arguments:
  repository            borg repository, mandatory is BORG_REPO is not set

optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -v, --verbose         print more details
  -x EXEC, --exec EXEC  execute the command on every matching file
  --md5                 also print file md5sum
  --sha1                also print file sha1sum
  -o FOLDER, --output FOLDER
                        extract matching files to this folder

archive selection:
  -A YYYY-MM-DD, --after YYYY-MM-DD
                        only consider archive created after given date
  -B YYYY-MM-DD, --before YYYY-MM-DD
                        only consider archive created before given date
  -P PREFIX, --prefix PREFIX
                        only consider archive names starting with this prefix.
  -R, --reverse         reverse the archives order, default is oldest first
  -F N, --first N       consider first N archives after other filters were
                        applied
  -L N, --last N        consider last N archives after other filters were
                        applied

file selection:
  -n MOTIF, --name MOTIF
                        select files with path containing MOTIF (ignore case)
  -r PATTERN, --regex PATTERN
                        select files with path matching PATTERN
  --new                 select only *new* files, which were not present in
                        previous archive
  --modified            select only modified files, which were different in
                        previous archive
```

## Find files in all archives

You can filter *files* in *archives* using:
* `--name MOTIF`: to select only files having `MOTIF` in their path (case not sensitive)
* `--regex PATTERN`: to select only files having their path matching the `PATTERN`
* `--new`: to only select file that were added in the archive, that were not present in the previous archive
* `--modified`: to only select file that were modified in the archive, that were present in the previous archive, but date or/and size changed

Examples:
```sh
# search files with .txt extension in all archives
$ borg-find --name '.txt' repo.borg

# search files with .txt extension that were modified in each archive
$ borg-find --name '.txt' --modified repo.borg

# search all new files with .txt extension in each archive
$ borg-find --name '.txt' --new repo.borg
```

## Find files in selected archives

You can also filter in which *archives* you will search for *files* using:
* `--after YYYY-MM-DD` to only consider *archives* created **after** the given date
* `--before YYYY-MM-DD` to only consider *archives* created **before** the given date
* `--prefix PREFIX` to only consider *archives* with a name starting with given *PREFIX*
* `--reverse`, by default *archives* are processed from the oldest to the newest, use this option to change the order
* `--last N` and `--first N` to only process the N **first** or **last** *archives*

> Note: **dates** can be date format `2020-02-24` or datetime format `2020-02-24T09:00:00`

Examples:
```sh
# search all log files in archives since february
$ borg-find --after '2020-02-01' --name '.log' repo.borg

# search all log files in the last 10 archive or march
$ borg-find --before '2020-03-31' --last 10 --name '.log' repo.borg
```

## Execute a command every on matching files

You can use `--exec` argument to execute a *shell* command (so you can pip commands like `--exec 'json_pp | grep "data" | wc -l'`)

Examples:
```sh
# to check since when logs contain a specific error message
$ borg-find \
    --after 2020-01-01 \
    --name ".log" \
    --exec "grep 'specific error message'" \
    repo.borg

# to count how many lines with word data do new json files contain
$ borg-find \
    --name ".json" \
    --new \
    --exec 'json_pp | grep "data" | wc -l' \
    --verbose \
    retpo.borg
```

## Extract matching files

You can also extract matching file using the `--output` argument
```sh
# extract all new jpg files from the last archive in a subfolder
$ borg-find --last 1 --new --name ".jpg" repo.borg --output new_files/
```


