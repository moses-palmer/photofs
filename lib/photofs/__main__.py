from photofs import *

def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog = 'photofs',
        add_help = True,
        description =
            'Explore tagged images from Shotwell in the file system.',
        epilog =
            'In addition to the command line options specified above, this '
            'program accepts all standard FUSE command line options.')

    parser.add_argument('mountpoint',
        help = 'The file system mount point.')

    parser.add_argument('--debug', '-d',
        help = 'Enable debug logging.',
        type = bool)

    parser.add_argument('--foreground', '-f',
        help = 'Run the daemon in the foreground.',
        action = 'store_true')

    class OAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string):
            try:
                name, value = values[0].split('=')
            except ValueError:
                name, value = values[0], True
            setattr(namespace, name, value)
    parser.add_argument('-o',
        help = 'Any FUSE options.',
        nargs = 1,
        action = OAction)

    # First, let args be the argument dict
    args = vars(parser.parse_args())

    # Then pop these known items and pass them on to the PhotoFS constructor
    photofs_args = {name: args.pop(name)
        for name in (
            'source',
            'database',
            'photo_path',
            'video_path',
            'date_format',
            'force_temporary',
            'sync_to')
        if not args.get(name, None) is None}

    # Then copy all non-None values and pass them to the FUSE constructor
    fuse_args = {name: value
        for name, value in args.items()
        if not value is None}

    try:
        photo_fs = PhotoFS(**photofs_args)
        fuse.FUSE(photo_fs, fsname = 'photofs', **fuse_args)
    except Exception as e:
        import traceback; traceback.print_exc()
        try:
            sys.stderr.write('%s\n' % e.args[0] % e.args[1:])
        except:
            sys.stderr.write('%s\n' % str(e))


main()
