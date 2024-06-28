const express = require('express');
const bodyParser = require('body-parser');
const mongoose = require('mongoose');
const app = express();

app.use(bodyParser.urlencoded({ extended: true }));

// Измените строку подключения на вашу существующую базу данных
mongoose.connect('mongodb://localhost:27017/groceryStoreDB', {
  useNewUrlParser: true,
  useUnifiedTopology: true
});

// Используйте существующие схемы и модели
const promotionSchema = new mongoose.Schema({
  title: String,
  description: String,
  start_date: Date,
  end_date: Date
});

const mailingSchema = new mongoose.Schema({
  email: String,
  subject: String,
  message: String,
  send_date: Date
});

const Promotion = mongoose.model('Promotion', promotionSchema);
const Mailing = mongoose.model('Mailing', mailingSchema);

// Обработчик для подписки на рассылку
app.post('/subscribe', (req, res) => {
  const newMailing = new Mailing({
    email: req.body.email,
    // Добавьте другие поля, если необходимо
  });
  newMailing.save((err) => {
    if (!err) {
      res.send('Успешно подписано!');
    } else {
      res.send(err);
    }
  });
});

app.listen(3000, function() {
  console.log('Сервер запущен на порту 3000');
});

// Обработчик событий для формы остается прежним
document.addEventListener('DOMContentLoaded', function() {
  const form = document.querySelector('.join__form');
  form.addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(form);
    fetch('/subscribe', {
      method: 'POST',
      body: formData
    })
    .then(response => response.text())
    .then(data => alert(data))
    .catch(error => console.error('Ошибка:', error));
  });
});
