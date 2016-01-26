BEEweb
=========

BEEweb provides a snappy web interface for controlling a Beeverycreative printer (BEETHEFIRST, BEETHEFIRST+, ...). It is Free Software
and released under the [GNU Affero General Public License V3](http://www.gnu.org/licenses/agpl.html).

This is based on the open-source project [Octoprint] (http://octoprint.org)


Installation & Dependencies
---------------------------

BEEweb depends on a couple of python modules to do its job. Those are automatically installed when installing
BEEweb via `setup.py`:

    python setup.py install

You should also do this every time after pulling from the repository, since the dependencies might have changed.

BEEweb currently only supports Python 2.7.

Usage
-----

Running the `setup.py` script via

    python setup.py install

installs the `beeweb` script in your Python installation's scripts folder
(which depending on whether you installed BEEweb globally or into a virtual env will be on your `PATH` or not). The
following usage examples assume that said `beeweb` script is on your `PATH`.

You can start the server via

    beeweb

By default it binds to all interfaces on port 5000 (so pointing your browser to `http://127.0.0.1:5000`
will do the trick). If you want to change that, use the additional command line parameters `host` and `port`,
which accept the host ip to bind to and the numeric port number respectively. If for example you want the server
to only listen on the local interface on port 8080, the command line would be

    beeweb --host=127.0.0.1 --port=8080

Alternatively, the host and port on which to bind can be defined via the configuration.

If you want to run BEEweb as a daemon (only supported on Linux), use

    beeweb --daemon {start|stop|restart} [--pid PIDFILE]

If you do not supply a custom pidfile location via `--pid PIDFILE`, it will be created at `/tmp/beeweb.pid`.

You can also specify the configfile or the base directory (for basing off the `uploads`, `timelapse` and `logs` folders),
e.g.:

    beeweb --config /path/to/another/config.yaml --basedir /path/to/my/basedir

See `beeweb --help` for further information.

BEEweb also ships with a `run` script in its source directory. You can also invoke that to start up the server, it
takes the same command line arguments as the `beeweb` script.

Configuration
-------------

If not specified via the commandline, the configfile `config.yaml` for BEEweb is expected in the settings folder,
which is located at `~/.beeweb` on Linux, at `%APPDATA%/BEEweb` on Windows and
at `~/Library/Application Support/BEEweb` on MacOS.

Please note that the most commonly used configuration settings can also easily
be edited from BEEweb's settings dialog.

If you want to customize the look of the application change the octoprint.less file under the static/less directory.
Install the tool lessc using npm, and compile the main less file using the following command line:

$ lessc -x octoprint.less ../css/octoprint.css

