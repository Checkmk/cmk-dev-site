#!groovy

/// file: release.groovy

def main() {
    def image_name = "python-curl-uv";
    def dockerfile = "ci/Dockerfile";
    def docker_args = "${mount_reference_repo_dir}";
    def release_new_version_flag = false;

    currentBuild.description += (
        """
        |Create an automatic release<br>
        |""".stripMargin());

    dir("${checkout_dir}") {
        def docker_image = docker.build(image_name, "-f ${dockerfile} .");
        docker_image.inside(docker_args) {
            stage("Create changelog") {
                sh(label: "create changelog", script: """
                    set -o pipefail
                    uv run \
                        changelog-generator \
                        changelog changelog.md \
                        --snippets=.snippets \
                        --in-place \
                        --version-reference="https://review.lan.tribe29.com/gitweb?p=checkmk_dev_tools.git;a=tag;h=refs/tags/"
                """);

                sh(label: "parse changelog", returnStdout: true, script: """
                    uv run \
                        changelog2version \
                        --changelog_file changelog.md \
                        --version_file cmk_dev_site/version.py \
                        --template_file ci/custom_version_template.py.template \
                        --print \
                        --output version.json
                """);
            }

            stage("Check tag exists") {
                withCredentials([sshUserPrivateKey(credentialsId: "release-checkmk", keyFileVariable: 'keyfile')]) {
                    withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile} -l release"]) {
                        release_new_version_flag = sh(script: """
                            git fetch --prune --prune-tags
                            CHANGELOG_VERSION=\$(jq -r .info.version version.json)
                            if [ \$(git tag -l "v\$CHANGELOG_VERSION") ]; then
                                echo "Tag v\$CHANGELOG_VERSION exits already"
                                exit 1
                            else
                                echo "Tag v\$CHANGELOG_VERSION does not yet exit"
                            fi
                        """, returnStatus: true) == 0;
                    }
                }
            }

            smart_stage(name: "Publish tag and Changelog", condition: release_new_version_flag, raiseOnError: false) {
                withCredentials([sshUserPrivateKey(credentialsId: "release-checkmk", keyFileVariable: 'keyfile')]) {
                    withEnv(["GIT_SSH_COMMAND=ssh -o \"StrictHostKeyChecking no\" -i ${keyfile} -l release"]) {
                        sh(label: "create and publish tag", returnStdout: true, script: """
                            cat version.json
                            CHANGELOG_VERSION=\$(jq -r .info.version version.json)
                            echo "Changelog version is: \$CHANGELOG_VERSION"

                            # this has to match with release and be added as "Forge Committer Identity"
                            # in the repo config with user "user/Check_MK release system (release)"
                            export GIT_AUTHOR_NAME="Checkmk release system"
                            export GIT_AUTHOR_EMAIL="noreply@checkmk.com"
                            export GIT_COMMITTER_NAME="Checkmk release system"
                            export GIT_COMMITTER_EMAIL="noreply@checkmk.com"
                            git fetch --prune --prune-tags

                            # create release branch and publish generated changelog
                            git checkout -b release/v\$CHANGELOG_VERSION
                            git add changelog.md cmk_dev_site/version.py
                            git commit -m "Add changelog for \$CHANGELOG_VERSION"
                            git push origin HEAD:release/\$CHANGELOG_VERSION

                            # adjust URL to this changelog in pyproject file, use double quotes for env variable usage
                            sed -i "s#CHANGE_ME_I_AM_A_CHANGELOG#release/\${CHANGELOG_VERSION}#" pyproject.toml

                            # create and publish tag
                            git tag -a v\$CHANGELOG_VERSION -m "v\$CHANGELOG_VERSION"
                            git tag --list
                            git push origin tag v\$CHANGELOG_VERSION
                        """);
                    }
                }
            }

            stage("Build package") {
                sh(label: "build package", script: """
                    # see comment in pyproject.toml
                    rm -rf dist/*
                    uv build
                    uv run twine check dist/*
                    python3 -m pip uninstall -y cmk-dev-site
                    python3 -m pip install --pre --user dist/cmk_dev_site-\$(grep -E "^__version__.?=" cmk_dev_site/version.py | cut -d '"' -f 2 | sed 's/-//g')-py3-none-any.whl
                """);
            }

            smart_stage(name: "Publish package", condition: release_new_version_flag, raiseOnError: false) {
                withCredentials([
                    string(credentialsId: 'PYPI_API_TOKEN_CMK_DEV_SITE_ONLY', variable: 'PYPI_API_TOKEN_CMK_DEV_SITE_ONLY')
                ]) {
                    sh(label: "publish package", script: """
                        uv publish \
                            --token "${PYPI_API_TOKEN_CMK_DEV_SITE_ONLY}"
                    """);
                }
            }
        }

        stage("Archive stuff") {
            show_duration("archiveArtifacts") {
                archiveArtifacts(
                    allowEmptyArchive: true,
                    artifacts: "dist/cmk_dev_site-*, changelog.md",
                    fingerprint: true,
                );
            }
        }
    }
}

return this;
