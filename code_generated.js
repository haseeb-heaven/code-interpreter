const fs = require('fs');

const filePath = '/Users/haseeb-mir/Downloads/db/Planets.json';

fs.readFile(filePath, 'utf8', (err, data) => {
  if (err) {
    console.error(err);
    return;
  }

  const jsonData = JSON.parse(data);

  console.log(JSON.stringify(jsonData, null, 4));
});
