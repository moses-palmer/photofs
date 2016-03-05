import sys

from photofs import *


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog='photofs',
        add_help=True,
        description='Explore tagged images from Shotwell in the file system.',
        epilog='In addition to the command line options specified above, this '
        'program accepts all standard FUSE command line options.')

    parser.add_argument(
        'mountpoint',
        help='The file system mount point.')

    parser.add_argument(
        '--debug', '-d',
        help='Enable debug logging.',
        type=bool)

    parser.add_argument(
        '--use-links', '-l',
        help='Report images as links. This will generally improve performance',
        action='store_true')

    parser.add_argument(
        '--foreground', '-f',
        help='Run the daemon in the foreground.',
        action='store_true')

    def filter_type(name, include):
        def inner(value):
            if filter_type.filters is None:
                return
            try:
                filter_type.filters[value] = include
            except AttributeError:
                filter_types.filters = {name: include}
        return inner
    filter_type.filters = {}

    parser.add_argument(
        '--photo-path',
        help='The name of the top level directory that contains photos.',
        default='Photos',
        type=filter_type(
            '--photo-path',
            lambda i:
            not i.is_video
            if isinstance(i, Image)
            else not i.has_video))

    parser.add_argument(
        '--video-path',
        help='The name of the top level directory that contains videos.',
        default='Videos',
        type=filter_type(
            '--video-path',
            lambda i:
            i.is_video
            if isinstance(i, Image)
            else i.has_video))

    class FlatPresentationAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string):
            filter_type.filters = None

    parser.add_argument(
        '--flat-presentation',
        nargs=0,
        help='Do not separate photos and videos.',
        action=FlatPresentationAction)

    parser.add_argument(
        '--date-format',
        help='The format to use for timestamps.')

    fuse_args = {}

    class OAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string):
            try:
                name, value = values[0].split('=')
            except ValueError:
                name, value = values[0], True
            fuse_args[name] = value
    parser.add_argument(
        '-o',
        help='Any FUSE options.',
        nargs=1,
        action=OAction)

    # Add image source specific command line arguments
    for source in ImageSource.SOURCES.values():
        source.add_arguments(parser)

    # First, let args be the argument dict, but remove undefined values
    args = {
        name: value
        for name, value in vars(parser.parse_args()).items()
        if value is not None}

    # Then pop these known items and pass them on to the FUSE constructor
    fuse_args.update({
        name: args.pop(name)
        for name in (
            'foreground',
            'debug')
        if name in args})

    try:
        photo_fs = PhotoFS(filters=filter_type.filters, **args)
        fuse.FUSE(photo_fs, args['mountpoint'], fsname='photofs', **fuse_args)
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            sys.stderr.write('%s\n' % e.args[0] % e.args[1:])
        except:
            sys.stderr.write('%s\n' % str(e))


main()
