function transform_timestamps(field_class) {
    var elements = document.getElementsByClassName(field_class);
    for(element of elements) {
        element.textContent = moment(element.textContent, 'X').format('HH:mm ddd, DD.MM.YYYY');
    }
}
