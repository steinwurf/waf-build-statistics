waf-build-statistics
====================

This repository contains the waf-build-statistics tool. The tool is meant
to be used with Steinwurf's waf which includes a custom dependency handling
utility.

The waf-build-statistics tool is included in a project by adding the following
to the wscript which is to be used with steinwurf's waf binary::


    def options(opt):

        import waflib.extras.wurf_dependency_bundle as bundle
        import waflib.extras.wurf_dependency_resolve as resolve

        bundle.add_dependency(opt, resolve.ResolveGitMajorVersion(
            name='waf-build-statistics',
            git_repository='github.com/steinwurf/waf-build-statistics.git',
            major_version=1))

    def configure(conf):

        if conf.is_toplevel():

            conf.load('wurf_dependency_bundle')
            conf.recurse(conf.dependency_path('waf-build-statistics'))

The main feature of the waf-build-statistics tool is to generate a json file
(located at the root of the build folder called build_statistics.json).
As an added bonus, the tool will also print a summary of changes after the build
finishes. Per default the summary will be based on the previous build, but this
can be changed by using the tool option ``compare_build``.

This is done like so::

    python waf --options=compare_build='some.json'

where ``some.json`` is the json file to compare with.

build_statistics.json has the following data design::

    {
        'source1': { size: 1 },
        'source2': { size: 2 },
        'source3': { size: 3 },
        'target1':
        {
            'time': 42,
            'size': 1337,
            'sources': ['source1', 'source2']
        },
        'target2':
        {
            'time': 113,
            'size': 859,
            'sources': ['source3']
        }
    }
