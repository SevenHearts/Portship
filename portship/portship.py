import os

from .vfs import VFSFile
from .ninja import Writer as NinjaWriter

CONVERSIONS = {
    '.dds': ('dds_to_png', '.png')
}

def generate_ninja(idx, dest):
    print('generating build configuration in: {}'.format(dest))
    print('reading IDX file at: {}'.format(idx.name))

    with idx:
        vfs = VFSFile(idx)

    ninja_path = os.path.join(dest, 'build.ninja')
    with open(ninja_path, 'w') as ninja_fd:
        ninja = NinjaWriter(ninja_fd, 1000)
        print('opened {} for writing'.format(ninja_path))

        ninja_fd.write('#\n')
        ninja.comment('Generated by Portship')
        ninja.comment('https://github.com/sevenhearts/portship')
        ninja_fd.write('#\n')
        ninja.comment('IDX file: {}'.format(vfs.path))
        ninja_fd.write('#\n')
        ninja.newline()
        print('wrote build header comments')

        ninja.variable('rose_path', vfs.dirpath)
        ninja.variable('raw_assets_path', 'raw_assets')
        ninja.variable('assets_path', 'assets')
        ninja.variable('util_path', 'util')
        ninja.variable('portship_path', os.path.dirname(__file__))
        ninja.newline()
        print('wrote build variables')

        extract = '$util_path/extract'

        ninja.rule('extract_vfs',
            command='{} $in $out $offset $length'.format(extract),
            description='Extract $out from $vfs_name')
        ninja.rule('extract_root_vfs',
            command='cp $in $out',
            description='Copy $out (ROOT.VFS entry)')
        ninja.rule('compile_c',
            command='cc -o $out $in -std=c99 -Werror -Wextra -Wall -pedantic -g0 -Os',
            description='Compile C program $out')
        ninja.rule('copy',
            command='cp $in $out',
            description='Copy $out')
        ninja.rule('dds_to_png',
            command='convert $in $out',
            description='Convert DDS: $out')
        ninja.newline()
        print('wrote build rules')

        ninja.build(
            rule='copy',
            outputs=['$util_path/extract.c'],
            inputs=['$portship_path/extract.c'])
        ninja.build(
            rule='compile_c',
            outputs=[extract],
            inputs=['$util_path/extract.c'])
        print('wrote extractor utility build rules')

        vfs_path = '$rose_path/{}'.format(os.path.relpath(vfs.path, vfs.dirpath))

        raw_assets = []

        for entry in vfs.entries.values():
            if entry.encrypted or entry.deleted or entry.compressed:
                continue

            output_path = entry.path.lower().replace('\\', '/')
            raw_output = '$raw_assets_path/{}'.format(output_path)

            raw_assets.append(raw_output)

            if entry.archive_path.lower() == 'root.vfs':
                # this means to read it directly from the filesystem
                ninja.build(
                    rule='extract_root_vfs',
                    outputs=[raw_output],
                    inputs=['$rose_path/{}'.format(entry.path.replace('\\', '/'))], # can't lower here since it may be case sensitive
                    implicit=[vfs_path, extract])
            else:
                ninja.build(
                    rule='extract_vfs',
                    outputs=[raw_output],
                    inputs=['$rose_path/{}'.format(entry.archive_path)],
                    implicit=[vfs_path, extract],
                    variables={
                        'length': entry.length,
                        'offset': entry.offset,
                        'vfs_name': entry.archive_path
                    })

            # conversion
            bare_path, ext = os.path.splitext(output_path)

            if ext in CONVERSIONS:
                rule, ext = CONVERSIONS[ext]

                ninja.build(
                    rule=rule,
                    outputs=['$assets_path/{}{}'.format(bare_path, ext)],
                    inputs=[raw_output])
            else:
                ninja.build(
                    rule='copy',
                    outputs=['$assets_path/{}'.format(output_path)],
                    inputs=[raw_output])

        ninja.newline()
        print('wrote extraction targets')

        ninja.build(
            rule='phony',
            outputs=['raw_assets'],
            inputs=raw_assets)
        print('wrote phony build targets')
        print('done')
