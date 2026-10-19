// Batch generation may bypass descriptor validationRegex; validate before reporting success.
def artifact = request.artifactId
if (!(artifact ==~ /[a-z][a-z0-9-]{1,39}/)) {
    throw new IllegalArgumentException('artifactId must contain 2-40 lowercase letters, digits or hyphens and start with a letter')
}
def packageSegment = artifact.replace('-', '_')
def reservedNames = ('abstract assert boolean break byte case catch char class const continue default ' +
        'do double else enum extends final finally float for goto if implements import instanceof int ' +
        'interface long native new package private protected public return short static strictfp super ' +
        'switch synchronized this throw throws transient try void volatile while true false null').split(' ') as Set
if (reservedNames.contains(packageSegment)) {
    throw new IllegalArgumentException('artifactId cannot be a Java reserved name: ' + artifact)
}
def expectedPackage = 'com.rain.' + packageSegment

// Never use request.package for file paths: IDEA can pass a literal Velocity expression.
// Java content already uses artifactId; relocate the fixed source directory to match it.
def generated = new File(request.outputDirectory, request.artifactId).canonicalFile
def outputRoot = new File(request.outputDirectory).canonicalFile.toPath()
if (!generated.toPath().startsWith(outputRoot) || generated.toPath() == outputRoot) {
    throw new IOException('Generated project must be inside outputDirectory')
}
['types', 'api', 'domain', 'infrastructure', 'trigger', 'app'].each { module ->
    def sourceSets = module == 'app' ? ['main', 'test'] : ['main']
    sourceSets.each { sourceSet ->
        def javaRoot = new File(generated, "app-backend/${artifact}-${module}/src/${sourceSet}/java").canonicalFile
        def source = new File(javaRoot, 'com/rain/project_template').canonicalFile
        def target = new File(javaRoot, 'com/rain/' + packageSegment).canonicalFile
        if (!source.toPath().startsWith(generated.toPath()) || !target.toPath().startsWith(generated.toPath())) {
            throw new IOException('Source package must stay inside generated project')
        }
        if (!source.isDirectory()) {
            throw new IOException('Missing template source directory: ' + source)
        }
        if (source != target) {
            java.nio.file.Files.move(source.toPath(), target.toPath())
        }
    }
}
println('Generated Maven groupId: com.autrain; Java package: ' + expectedPackage)

// Archetype requires a root pom during generation; the project reactor lives in app-backend/.
def descriptor = new File(generated, 'pom.xml')
assert new File(generated, 'app-backend/pom.xml').isFile()
assert descriptor.parentFile == generated
if (descriptor.exists() && !descriptor.delete()) {
    throw new IOException('Cannot remove generation-only root pom.xml')
}

def ignoreTemplate = new File(generated, 'gitignore.template')
assert ignoreTemplate.isFile()
if (!ignoreTemplate.renameTo(new File(generated, '.gitignore'))) {
    throw new IOException('Cannot create .gitignore')
}
