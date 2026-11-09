// Batch generation may bypass descriptor validationRegex; validate before reporting success.
def artifact = request.artifactId
if (!(artifact ==~ /[a-z][a-z0-9-]{1,39}/)) {
    throw new IllegalArgumentException('artifactId must contain 2-40 lowercase letters, digits or hyphens and start with a letter')
}
def database = request.properties.getProperty('databaseName', 'auto')
if (database == 'auto') {
    database = artifact.replace('-', '_')
}
if (!(database ==~ /[a-z][a-z0-9_]{0,47}/)) {
    throw new IllegalArgumentException('databaseName must contain 1-48 lowercase letters, digits or underscores and start with a letter')
}
if (database in ['mysql', 'sys', 'information_schema', 'performance_schema', 'nacos_config', 'xxl_job']) {
    throw new IllegalArgumentException('databaseName conflicts with a system or middleware database: ' + database)
}
println('Generated database: ' + database)

def packageSegment = artifact.replace('-', '_')
def reservedNames = ('abstract assert boolean break byte case catch char class const continue default ' +
        'do double else enum extends final finally float for goto if implements import instanceof int ' +
        'interface long native new package private protected public return short static strictfp super ' +
        'switch synchronized this throw throws transient try void volatile while true false null').split(' ') as Set
if (reservedNames.contains(packageSegment)) {
    throw new IllegalArgumentException('artifactId cannot be a Java reserved name: ' + artifact)
}

// Java packages default to "<groupId>.<artifactId>"; an explicit package property overrides the root package.
// Hyphens are legal in Maven coordinates but not in Java package names.
def groupPackage = request.groupId.replace('-', '_')
if (!(groupPackage ==~ /[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*/)) {
    throw new IllegalArgumentException('groupId must form a valid Java package after replacing hyphens: ' + request.groupId)
}
groupPackage.split('\\.').each { segment ->
    if (reservedNames.contains(segment)) {
        throw new IllegalArgumentException('groupId segment cannot be a Java reserved name: ' + segment)
    }
}
def derivedPackage = groupPackage + '.' + packageSegment

// IDEA may forward old cached defaults, a bare -Dpackage, or a literal Velocity expression.
def requestedPackage = request.properties.getProperty('package', 'auto')
def legacyPackageValues = ['', 'auto', 'true', 'com.rain', 'com.autrain']
def useDerivedPackage = requestedPackage == null || legacyPackageValues.contains(requestedPackage) || requestedPackage.contains('${')
def rootPackage = derivedPackage
if (!useDerivedPackage) {
    rootPackage = requestedPackage.replace('-', '_')
    if (!(rootPackage ==~ /[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*/)) {
        throw new IllegalArgumentException('package must be a valid Java package after replacing hyphens: ' + requestedPackage)
    }
    rootPackage.split('\\.').each { segment ->
        if (reservedNames.contains(segment)) {
            throw new IllegalArgumentException('package segment cannot be a Java reserved name: ' + segment)
        }
    }
}
def expectedPackage = rootPackage

// Java content is filtered with the derived package; relocate sources and rewrite them to the root package.
def rootPath = rootPackage.replace('.', '/')
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
        def target = new File(javaRoot, rootPath).canonicalFile
        if (!source.toPath().startsWith(generated.toPath()) || !target.toPath().startsWith(generated.toPath())) {
            throw new IOException('Source package must stay inside generated project')
        }
        if (!source.isDirectory()) {
            throw new IOException('Missing template source directory: ' + source)
        }
        if (source != target) {
            java.nio.file.Files.createDirectories(target.parentFile.toPath())
            java.nio.file.Files.move(source.toPath(), target.toPath())
            // Drop the now-empty com/rain template path so generated projects contain only the real package.
            def empty = source.parentFile
            while (empty != null && empty.toPath() != javaRoot.toPath() && empty.isDirectory() && empty.listFiles().length == 0) {
                if (!empty.delete()) {
                    throw new IOException('Cannot remove empty template directory: ' + empty)
                }
                empty = empty.parentFile
            }
        }
    }
}
if (rootPackage != derivedPackage) {
    def textExtensions = ['.java', '.xml', '.md', '.yml', '.yaml', '.properties', '.json', '.ts', '.tsx',
                          '.html', '.css', '.sh', '.ps1', '.template', '.example', '.editorconfig', '.gitattributes', '.gitignore']
    generated.eachFileRecurse(groovy.io.FileType.FILES) { file ->
        if (textExtensions.any { file.name.endsWith(it) }) {
            def text = file.getText('UTF-8')
            if (text.contains(derivedPackage)) {
                file.setText(text.replace(derivedPackage, rootPackage), 'UTF-8')
            }
        }
    }
}
println('Generated Maven groupId: ' + request.groupId + '; Java package: ' + expectedPackage)

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

// Maven uses host-native line endings while filtering. Linux container entrypoints
// must receive LF even when the project is generated by IDEA on Windows.
generated.eachFileRecurse(groovy.io.FileType.FILES) { file ->
    if (file.name.endsWith('.sh')) {
        def content = file.getText('UTF-8')
        file.setText(content.replace('\r\n', '\n').replace('\r', '\n'), 'UTF-8')
    }
}
