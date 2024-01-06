echo "Cleaning up..."
rm -rf build dist *.egg-info    # clean up
sleep 1
echo "Building..."
python setup.py sdist bdist_wheel # build
sleep 1
echo "Copying to wheelz..."
cp -f dist/* /Users/haseeb-mir/Downloads/wheelz/dist # copy and overwrite files to wheelz
sleep 1
echo "Done."
