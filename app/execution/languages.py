"""Per-language build and run recipes.

Adding a language is a matter of appending one :class:`LanguageSpec` - neither
sandbox backend contains language-specific branching.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import Language


@dataclass(frozen=True, slots=True)
class LanguageSpec:
    id: str
    display_name: str
    source_filename: str
    #: Argv used to compile, or ``None`` for interpreted languages.
    compile_cmd: list[str] | None
    #: Argv used to execute the (possibly compiled) program.
    run_cmd: list[str]
    #: Image used by the Docker backend.
    docker_image: str
    #: Executables the local backend needs on ``PATH``.
    local_requirements: tuple[str, ...]
    #: Extension used for the compiled artefact, if any.
    artifact: str | None = None
    #: The JVM reserves a huge virtual address space at startup, so capping
    #: RLIMIT_AS kills it outright. Such languages self-limit instead.
    supports_address_space_limit: bool = True
    #: Extra argv injected before ``run_cmd`` args, templated with the limits.
    memory_flag_template: list[str] = field(default_factory=list)

    @property
    def needs_compile(self) -> bool:
        return self.compile_cmd is not None

    def render_run_cmd(self, memory_limit_mb: int) -> list[str]:
        """Run argv with any language-level memory flag substituted in."""
        if not self.memory_flag_template:
            return list(self.run_cmd)
        flags = [
            part.replace("{memory_mb}", str(memory_limit_mb))
            for part in self.memory_flag_template
        ]
        # Flags belong immediately after the interpreter/launcher binary.
        return [self.run_cmd[0], *flags, *self.run_cmd[1:]]


LANGUAGES: dict[str, LanguageSpec] = {
    Language.PYTHON.value: LanguageSpec(
        id=Language.PYTHON.value,
        display_name="Python 3.11",
        source_filename="solution.py",
        # Byte-compiling first turns a SyntaxError into a Compilation Error
        # verdict rather than a confusing Runtime Error.
        compile_cmd=["python", "-m", "py_compile", "solution.py"],
        run_cmd=["python", "solution.py"],
        docker_image="python:3.11-slim",
        local_requirements=("python",),
    ),
    Language.CPP.value: LanguageSpec(
        id=Language.CPP.value,
        display_name="C++17 (GCC)",
        source_filename="solution.cpp",
        compile_cmd=[
            "g++",
            "-std=c++17",
            "-O2",
            "-pipe",
            "-static",
            "-s",
            "-o",
            "solution",
            "solution.cpp",
        ],
        run_cmd=["./solution"],
        docker_image="gcc:13",
        local_requirements=("g++",),
        artifact="solution",
    ),
    Language.JAVA.value: LanguageSpec(
        id=Language.JAVA.value,
        display_name="Java 21",
        source_filename="Main.java",
        compile_cmd=["javac", "-encoding", "UTF-8", "Main.java"],
        run_cmd=["java", "-cp", ".", "Main"],
        # Kept in step with the JDK baked into the Dockerfile, so a submission
        # behaves identically on either backend.
        docker_image="eclipse-temurin:21-jdk",
        local_requirements=("javac", "java"),
        artifact="Main.class",
        supports_address_space_limit=False,
        memory_flag_template=["-Xmx{memory_mb}m", "-XX:+UseSerialGC", "-Xss64m"],
    ),
}


def get_language(language_id: str) -> LanguageSpec:
    try:
        return LANGUAGES[language_id.strip().lower()]
    except KeyError as exc:
        supported = ", ".join(sorted(LANGUAGES))
        raise ValueError(
            f"Unsupported language {language_id!r}. Supported: {supported}"
        ) from exc


def supported_languages() -> list[dict]:
    return [
        {
            "id": spec.id,
            "name": spec.display_name,
            "compiled": spec.needs_compile,
            "docker_image": spec.docker_image,
        }
        for spec in LANGUAGES.values()
    ]
