#!/bin/bash
#               OpenCenter(TM) is Copyright 2013 by Rackspace US, Inc.
##############################################################################
#
# OpenCenter is licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.  This
# version of OpenCenter includes Rackspace trademarks and logos, and in
# accordance with Section 6 of the License, the provision of commercial
# support services in conjunction with a version of OpenCenter which includes
# Rackspace trademarks and logos is prohibited.  OpenCenter source code and
# details are available at: # https://github.com/rcbops/opencenter or upon
# written request.
#
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0 and a copy, including this
# notice, is available in the LICENSE file accompanying this software.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the # specific language governing permissions and limitations
# under the License.
#
##############################################################################

function usage {
  echo "Usage: $0 [OPTION]..."
  echo "Run the OpenCenterAgent test suite(s)"
  echo ""
  echo "  -V, --virtual-env        Always use virtualenv.  Install automatically if not present"
  echo "  -N, --no-virtual-env     Don't use virtualenv.  Run tests in local environment"
  echo "  -f, --force              Force a clean re-build of the virtual environment. Useful when dependencies have been added."
  echo "  -p, --pep8               Just run pep8"
  echo "  -c, --coverage           Generate coverage report"
  echo "  -I, --no-integration     Don't run integration tests."
  echo "  -H, --html               Generate coverage report html, if -c"
  echo "  -h, --help               Print this usage message"
  echo ""
  echo "Note: with no options specified, the script will try to run the tests in a virtual environment,"
  echo "      If no virtualenv is found, the script will ask if you would like to create one.  If you "
  echo "      prefer to run tests NOT in a virtual environment, simply pass the -N option."
  exit
}

function process_option {
  case "$1" in
    -h|--help) usage;;
    -V|--virtual-env) always_venv=1; never_venv=0;;
    -N|--no-virtual-env) always_venv=0; never_venv=1;;
    -f|--force) force=1;;
    -p|--pep8) just_pep8=1;;
    -c|--coverage) coverage=1;;
    -H|--html) html=1;;
    -I|--no-integration) integration=false;;

    -*) noseopts="$noseopts $1";;
    *) noseargs="$noseargs $1"
  esac
}

venv=.venv
with_venv=tools/with_venv.sh
always_venv=0
never_venv=0
force=0
integration=true
#no_site_packages=0
# installvenvopts=
noseargs=
noseopts="-v --with-xunit"
wrapper=""
just_pep8=0
coverage=0
html=0
integration_tmp_dir=.integration_tmp

for arg in "$@"; do
  process_option $arg
done

# If enabled, tell nose to collect coverage data
if [ $coverage -eq 1 ]; then
    noseopts="$noseopts --with-coverage --cover-package=opencenteragent"
fi

function run_tests {
  # Cleanup *pyc
  ${wrapper} find . -type f -name "*.pyc" -delete
  # Just run the test suites in current environment
  ${wrapper} $NOSETESTS
  RESULT=$?
  if [ "$RESULT" -ne "0" ];
  then
    exit 1
  #  ERRSIZE=`wc -l run_tests.log | awk '{print \$1}'`
  #  if [ "$ERRSIZE" -lt "40" ];
  #  then
  #      cat run_tests.log
  #  fi
  fi
  return $RESULT
}

function run_pep8 {
  echo "Running pep8 ..."
  PEP8_EXCLUDE=".venv"
  PEP8_OPTIONS="--exclude=$PEP8_EXCLUDE --repeat --show-pep8 --show-source"
  PEP8_INCLUDE="."
  ${wrapper} pep8 $PEP8_OPTIONS $PEP8_INCLUDE || exit 1
}

run_integration(){ 
  trap integration_cleanup INT TERM EXIT
  pushd $integration_tmp_dir
    $with_venv curl https://raw.github.com/rcbops/opencenter-install-scripts/sprint/install-dev.sh\
      | bash -s --role=server --ip=127.0.01  
    pushd opencenter-agent
      git pull ../../ sprint 
      $with_venv python setup.py install
    popd # agent dir 
  popd # integration tmp dir
  trap - INT TERM EXIT
  # integration_cleanup
}

integration_cleanup(){
 [ -d $integration_tmp_dir ] && rm -rf $integration_tmp_dir
 
}


NOSETESTS="nosetests $noseopts $noseargs tests/*.py"

if [ $never_venv -eq 0 ]
then
  # Remove the virtual environment if --force used
  if [ $force -eq 1 ]; then
    echo "Cleaning virtualenv..."
    rm -rf ${venv}
  fi
  if [ -e ${venv} ]; then
    wrapper="${with_venv}"
  else
    if [ $always_venv -eq 1 ]; then
      # Automatically install the virtualenv
      env python tools/install_venv.py
      wrapper="${with_venv}"
    else
      echo -e "No virtual environment found...create one? (Y/n) \c"
      read use_ve
      if [ "x$use_ve" = "xY" -o "x$use_ve" = "x" -o "x$use_ve" = "xy" ]; then
        # Install the virtualenv and run the test suite in it
        env python tools/install_venv.py
        wrapper=${with_venv}
      fi
    fi
  fi
fi

# Delete old coverage data from previous runs
if [ $coverage -eq 1 ]; then
    ${wrapper} coverage erase
fi

if [ $just_pep8 -eq 1 ]; then
    run_pep8
    exit
fi

# run_tests || exit
run_tests

if [ $coverage -eq 1 ]; then
    echo "Generating coverage report in coverage/"
    # Don't compute coverage for common code, which is tested elsewhere
    [ $html -eq 1 ] && ${wrapper} coverage html --include='opencenteragent/*' -d coverage -i
    ${wrapper} coverage xml --include='opencenteragent/*' -i
fi

run_integration
