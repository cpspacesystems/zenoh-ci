# Zenoh CI PoC

Meant to serve as an example of a typical multi-language Zenoh project and
to demonstrate we can configure basic CI functionality.

## Quickstart

Install Bazel and Bazelisk by following the instructions on the [Bazel website](https://bazel.build/install/bazelisk#updating_bazel).

Then run:

```bash
bazelisk build //...

# In separate windows, tmux panes, etc:
bazelisk run //rust_nodes/pub_test:pub
bazelisk run //rust_nodes/sub_test:sub
```

## Bazel and Bazelisk

This project uses [Bazel](https://github.com/bazelbuild/bazel/blob/master/README.md) as a polyglot build system and [Bazelisk](https://github.com/bazelbuild/bazelisk/blob/master/README.md) to manage Bazel versions.

The USE_BAZEL_VERSION flag in `.bazeliskrc` specifies the Bazel version used when commands like `bazelisk build //...` are run.

Bazel is configured to ingest all Cargo.toml packages specified in `/MODULE.bazel`:

```bazel
crate.from_cargo(
    name = "crates",
    manifests = ["//rust_nodes/pub_test:Cargo.toml", "//rust_nodes/sub_test:Cargo.toml"],
)
```

When writing a new Rust package, add its `Cargo.toml` path to this list and collect deps using this boilerplate:

```bazel
load("@crates//:defs.bzl", "all_crate_deps", "aliases")

# ...

rust_binary(
    name = "<package_name>",
    srcs = ["src/main.rs"],
    edition = "2021",
    aliases = aliases(),
    deps = all_crate_deps(normal = True),
)
```
